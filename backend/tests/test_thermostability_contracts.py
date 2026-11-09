"""Scientific evidence boundaries for thermostability tools (no model downloads)."""

import pytest


def test_esm_requires_explicit_candidates(monkeypatch):
    from app.tools.esm2_predict import esm2_predict

    result = esm2_predict("ACDEF")
    assert result["status"] == "blocked"
    assert result["blocked_reason"] == "mutations_required"
    assert result["required_inputs"] == ["mutations"]
    assert result["is_real_inference"] is False


def test_esm_scores_actual_wild_type_context_and_labels_it(monkeypatch):
    import sys
    import importlib.util
    from contextlib import nullcontext
    from pathlib import Path
    from types import SimpleNamespace

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(no_grad=nullcontext))
    spec = importlib.util.spec_from_file_location(
        "thermostability_test_embeddings", Path(__file__).parents[1] / "app/ml/embeddings.py",
    )
    embeddings = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(embeddings)

    captured = []

    class Alphabet:
        def get_batch_converter(self):
            return lambda batch: (None, None, [[0, 1, 2, 3, 4, 5, 0]])

        def get_idx(self, aa):
            return "ACDEF".index(aa)

    def model(tokens):
        captured.append(tokens)

        class Logits:
            def __getitem__(self, index):
                return 2.0 if index == (0, 1, 1) else 0.0

        return {"logits": Logits()}

    monkeypatch.setattr(embeddings, "_get_esm2", lambda: {
        "model": model, "alphabet": Alphabet(), "name": "fake_esm2",
    })
    result = embeddings.score_mutations("ACDEF", ["A1C"])
    assert captured == [[[0, 1, 2, 3, 4, 5, 0]]]
    assert result["mutations"][0]["score"] == 2.0
    assert result["scoring_strategy"] == "wild_type_marginal"
    assert "masked" not in result["method"]
    assert result["is_thermostability_prediction"] is False


async def test_stability_lookup_discloses_local_scope_truncation_and_raw_signs(session):
    from app.models.domain import EnzymeRecord, StabilityRecord
    from app.tools.data_lookup import get_stability_data

    enzyme = EnzymeRecord(uniprot_id="P00123", sequence="ACDEF", seq_length=5)
    session.add(enzyme)
    await session.flush()
    session.add_all([
        StabilityRecord(enzyme_id=enzyme.id, mutation=f"A{i + 1}V", mutation_pos=i + 1,
                        wild_type="A", mutant="V", ddg=[1.0, -1.0, 0.0, None][i % 4],
                        source_db="protherm", literature_ref="PMID:12345")
        for i in range(101)
    ])
    await session.flush()

    result = await get_stability_data(" p00123 ", _session=session)
    assert result["found"] is True
    assert result["total_available"] == 101
    assert result["returned_count"] == result["total_records"] == 100
    assert result["truncated"] is True
    assert result["scope"]["external_search_performed"] is False
    assert result["scope"]["match"] == "exact_uniprot_id"
    import hashlib
    assert result["protein_sequence_sha256"] == hashlib.sha256(b"ACDEF").hexdigest()
    assert result["source_coordinate_system"] == "record_sequence_1based"
    assert result["records"][0]["source_db"] == "protherm"
    assert result["records"][0]["literature_ref"] == "PMID:12345"
    assert result["ddg_sign_counts"] == {"positive": 25, "negative": 25, "zero": 25, "missing": 25}
    assert result["ddg_direction"] == "unknown"
    assert result["stabilizing"] is None
    assert result["destabilizing"] is None


@pytest.mark.parametrize("sequence", [" aCd\nEf ", ""])
async def test_stability_lookup_existing_protein_without_records_is_no_hit(session, sequence):
    from app.models.domain import EnzymeRecord
    from app.tools.data_lookup import get_stability_data

    session.add(EnzymeRecord(uniprot_id="P00123", sequence=sequence, seq_length=5))
    await session.flush()
    result = await get_stability_data("P00123", _session=session)
    assert result["found"] is False
    assert result["status"] == "no_hit"
    assert result["total_available"] == result["returned_count"] == 0
    assert result["scope"]["external_search_performed"] is False
    import hashlib
    assert result["protein_sequence_sha256"] == (hashlib.sha256(b"ACDEF").hexdigest() if sequence else None)
    assert result["source_coordinate_system"] == "record_sequence_1based"


async def test_stability_lookup_rejects_unsafe_input_before_database_access():
    from app.tools.data_lookup import get_stability_data

    result = await get_stability_data("P00123' OR 1=1 --")
    assert result["status"] == "needs_input"
    assert result["found"] is False


@pytest.mark.parametrize("distances,feedback", [
    ({}, {}),
    ({"A10V:D80N": 22.0}, {}),
    ({}, {"A10V": {"decision": "go"}, "D80N": {"decision": "go"}}),
])
async def test_combination_missing_evidence_never_go(distances, feedback):
    from app.tools.mutation_epistasis_check import mutation_epistasis_check

    result = await mutation_epistasis_check(
        ["A10V", "D80N"], structural_distances=distances,
        single_mutant_feedback=feedback,
    )
    assert result["recommendation"] == "watch"
    assert result["required_missing_evidence"]
    assert result["combination_effect"] == "unvalidated"


@pytest.mark.parametrize("mutations", [["A10V", "A10G"], ["A0V", "D80N"], ["B10V", "D80N"], ["A10A", "D80N"], ["A10V", "A10V"]])
async def test_combination_blocks_invalid_or_mutually_exclusive_substitutions(mutations):
    from app.tools.mutation_epistasis_check import mutation_epistasis_check

    result = await mutation_epistasis_check(mutations)
    assert result["status"] == "blocked"
    assert result["combination_effect"] == "unvalidated"


async def test_combination_go_means_experiment_only():
    from app.tools.mutation_epistasis_check import mutation_epistasis_check

    result = await mutation_epistasis_check(
        ["A10V", "D80N"], structural_distances={"A10V:D80N": 22.0},
        single_mutant_feedback={"A10V": {"decision": "go"}, "D80N": {"decision": "go"}},
    )
    assert result["recommendation"] == "go"
    assert result["combination_effect"] == "unvalidated"
    assert result["recommendation_scope"] == "prioritize_combination_experiment_only"


async def test_invalid_distance_does_not_count_as_structural_evidence():
    from app.tools.mutation_epistasis_check import mutation_epistasis_check

    result = await mutation_epistasis_check(
        ["A10V", "D80N"], structural_distances={"A10V:D80N": float("nan")},
        single_mutant_feedback={"A10V": {"decision": "go"}, "D80N": {"decision": "go"}},
    )
    assert result["recommendation"] == "watch"
    assert "pairwise_structural_distances" in result["required_missing_evidence"]


def test_knowledge_graph_never_assigns_unverified_ddg_effect_direction():
    from app.services.knowledge_graph import EnzymeKnowledgeGraph

    text = EnzymeKnowledgeGraph(None).to_natural_language({
        "uniprot_id": "P00123", "stability_records": [
            {"mutation": "A1V", "ddg": 1.0},
            {"mutation": "A2V", "ddg": -1.0},
            {"mutation": "A3V", "ddg": 0.0},
        ],
    })
    assert "positive=1, negative=1, zero=1" in text
    assert "does not record the sign convention" in text
    assert "Stabilizing:" not in text
