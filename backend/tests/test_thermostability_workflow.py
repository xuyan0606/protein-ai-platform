"""Scientific boundary and deterministic candidate-screen regression cases."""
import hashlib

import pytest

from app.services.thermostability_workflow import build_screen


SEQ = "ACDEG"
SHA = hashlib.sha256(SEQ.encode()).hexdigest()
OBJECTIVE = {"endpoint": "tm", "method": "DSC", "ph": 7.0, "substrate": "none",
             "buffer": "phosphate", "cofactors": "none", "min_activity_retention_pct": 80}
IDENTITY = {"identity_status": "identified", "guardrail": {"status": "ready"},
            "query": {"sequence_sha256": SHA}, "protected_positions": [2]}
MODULE = {"status": "ready", "candidate_output_allowed": True, "objective": "thermostability"}


def screen(**changes):
    args = dict(sequence=SEQ, objective=OBJECTIVE, identity_profile=IDENTITY,
                objective_module_plan=MODULE, mutations=["D3N", "A1V", "C2A", "A1V"])
    args.update(changes)
    return build_screen(**args)


def atom(serial, aa, number, x, chain="A", atom_name="CA", record="ATOM", insertion=""):
    return (f"{record:<6}{serial:5d} {atom_name:^4} {aa:3s} {chain}{number:4d}{insertion:1s}   "
            f"{x:8.3f}{0:8.3f}{0:8.3f}{1:6.2f}{95:6.2f}          C ")


def pdb():
    return "\n".join(atom(i, aa, 100+i, i*10) for i, aa in enumerate(
        ["ALA", "CYS", "ASP", "GLU", "GLY"], 1))


def test_requires_endpoint_conditions_and_activity_preservation():
    result = screen(objective={"endpoint": "optimal_temperature"})
    assert result["status"] == "needs_input"
    assert not result["candidates"]
    assert "endpoint" in result["required_inputs"]
    assert "min_activity_retention_pct" in result["required_inputs"]


def test_identity_must_be_bound_to_the_exact_sequence():
    result = screen(identity_profile={**IDENTITY, "query": {"sequence_sha256": "other"}})
    assert result["status"] == "blocked"
    assert not result["candidates"]
    assert "identity_sequence_mismatch" in result["blockers"]


def test_union_is_deterministic_without_literature_and_protects_function():
    result = screen(candidate_sources=[{"kind": "consensus", "reference": "reviewed MSA v1",
                "sequence_sha256": SHA, "mutations": ["D3N", "E4D"]}])
    assert [r["mutation"] for r in result["candidates"]] == ["A1V", "D3N", "E4D"]
    assert result["rejected"][0]["mutation"] == "C2A"
    assert "identity_protected" in result["rejected"][0]["reasons"]
    assert len(next(r for r in result["candidates"] if r["mutation"] == "D3N")["sources"]) == 2
    assert result["experimental_plan"]["controls"] == ["WT"]
    assert result["experimental_plan"]["combination_design"] == "after_single_mutant_feedback"


def test_source_from_another_protein_is_never_projected_by_position():
    result = screen(mutations=[], candidate_sources=[{"kind": "literature", "reference": "paper",
                  "sequence_sha256": "wrong", "mutations": ["A1V"]}])
    assert result["candidates"] == []
    assert "source_sequence_mismatch" in result["source_issues"]


def test_full_chain_mapping_preserves_author_number_and_plddt_semantics():
    result = screen(pdb_data=pdb(), structure_source="colabfold", full_length_start=21)
    row = result["candidates"][0]
    assert row["structure_position"] == {"chain_id": "A", "residue_number": 101, "insertion_code": None}
    assert row["full_length_position"] == 21
    assert result["structure"]["bfactor_semantics"] == "plddt_not_flexibility"
    assert all("b_factor" not in r["sources"] for r in result["candidates"])


def test_partial_or_wrong_structure_does_not_silently_use_coordinate_order():
    result = screen(pdb_data="\n".join(pdb().splitlines()[1:]))
    assert result["status"] == "blocked"
    assert "structure_numbering_mapping_required" in result["blockers"]


def test_explicit_mapping_must_match_structure_wt_and_be_one_to_one():
    rows = [{"source_position": p, "target_position": 101, "target_chain_id": "A",
             "confidence": "exact", "user_confirmed": True} for p in [1, 3]]
    result = screen(pdb_data=pdb(), mapping_rows=rows)
    assert result["status"] == "blocked"
    assert "invalid_structure_mapping" in result["blockers"]


@pytest.mark.parametrize("field,value", [("target_chain_id", ["A"]), ("target_insertion_code", ["B"]),
                                        ("confidence", {"value": "exact"}), ("source_scheme", ["input_sequence"])])
def test_malformed_mapping_field_is_controlled(field, value):
    row = {"source_position": 1, "target_position": 101, "target_chain_id": "A",
           "confidence": "exact", "user_confirmed": True, field: value}
    result = screen(pdb_data=pdb(), mapping_rows=[row])
    assert result["status"] == "blocked"
    assert "invalid_structure_mapping" in result["blockers"]


def test_metal_is_protected_ligand_and_other_chain_contacts_require_review():
    structure = pdb() + "\n" + atom(9, "ZN", 500, 30.5, atom_name="ZN", record="HETATM")
    result = screen(pdb_data=structure, mutations=["D3N", "A1V"])
    assert [r["mutation"] for r in result["candidates"]] == ["A1V"]
    assert "metal_coordination_geometry" in result["rejected"][0]["reasons"]
    structure = pdb() + "\n" + atom(9, "LIG", 500, 10.5, record="HETATM")
    result = screen(pdb_data=structure, mutations=["A1V"])
    assert "ligand_contact" in result["candidates"][0]["risks"]
    assert result["candidates"][0]["manual_review_required"] is True


def test_bounded_scan_is_explicit_and_cannot_hide_truncation():
    result = screen(mutations=[], candidate_positions=[1, 3], assay_budget=2)
    assert result["candidate_counts"]["generated"] == 38
    assert result["candidate_counts"]["eligible"] == 38
    assert len(result["experimental_plan"]["single_mutants"]) == 2
    assert len(result["candidates"]) == 38


@pytest.mark.parametrize("mutation", ["A0V", "A1A", "V1A", "A999V", "A1X"])
def test_invalid_or_wt_mismatch_is_rejected(mutation):
    result = screen(mutations=[mutation])
    assert result["candidates"] == []
    assert result["rejected"]


@pytest.mark.asyncio
async def test_missing_optional_prediction_keeps_hypotheses_with_separate_status(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    from app.tools import thermostability_adapters

    async def unavailable(*args, **kwargs):
        return {"status": "blocked", "blocked_reason": "service_not_configured", "predictions": []}

    monkeypatch.setattr(thermostability_adapters, "ddgun_predict", unavailable)
    result = await thermostability_candidate_workflow(
        sequence=SEQ, objective=OBJECTIVE, identity_profile=IDENTITY,
        objective_module_plan=MODULE, mutations=["A1V"], run_ddgun=True)
    assert result["status"] == "partial"
    assert result["candidates"][0]["mutation"] == "A1V"
    assert result["candidates"][0]["scores"]["ddgun"] is None
    assert result["branches"]["ddgun"]["status"] == "blocked"
    assert result["experimental_plan"]["controls"] == ["WT"]


def esm_response(codes, scores=None):
    return {"is_real_inference": True, "is_thermostability_prediction": False,
            "model": "ESM-2-test", "method": "zero-shot wild-type marginal log-odds",
            "scoring_strategy": "wild_type_marginal",
            "mutations": [{"mutation": code, "score": (scores or {}).get(code, 1.0)} for code in codes]}


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, [], {"is_real_inference": True, "mutations": [None]},
    {"is_real_inference": True, "mutations": [{"mutation": "A1V", "score": True}]},
    {"is_real_inference": True, "mutations": [{"mutation": "A1V", "score": float("nan")}]},
    {"is_real_inference": True, "mutations": [{"mutation": "A1V", "score": float("inf")}]},
])
async def test_malformed_optional_esm_is_blocked_without_losing_candidates(monkeypatch, bad):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    import importlib
    esm = importlib.import_module("app.tools.esm2_predict")
    monkeypatch.setattr(esm, "esm2_predict", lambda *a: bad)
    result = await thermostability_candidate_workflow(
        sequence=SEQ, objective=OBJECTIVE, identity_profile=IDENTITY,
        objective_module_plan=MODULE, mutations=["A1V"], run_esm=True)
    assert result["status"] == "partial"
    assert result["candidates"][0]["mutation"] == "A1V"
    assert result["candidates"][0]["scores"]["esm_preference"] is None
    assert result["branches"]["esm"]["status"] == "blocked"
    assert result["branches"]["esm"]["mutations"] == []


@pytest.mark.asyncio
async def test_optional_esm_exception_keeps_prior_ddgun_evidence(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    from app.tools import thermostability_adapters
    import importlib
    esm = importlib.import_module("app.tools.esm2_predict")

    def fail(*args):
        raise RuntimeError("private-model-environment-details")

    async def ddgun(sequence, codes, pdb_data="", chain_id="A"):
        assert not pdb_data
        return {"status": "completed", "predictions": [{"mutation": code, "ddg": 1.2,
                "unit": "kcal/mol", "direction": "positive=increased unfolding stability"} for code in codes]}

    monkeypatch.setattr(esm, "esm2_predict", fail)
    monkeypatch.setattr(thermostability_adapters, "ddgun_predict", ddgun)
    result = await thermostability_candidate_workflow(
        sequence=SEQ, objective=OBJECTIVE, identity_profile=IDENTITY,
        objective_module_plan=MODULE, mutations=["A1V"], run_ddgun=True, run_esm=True, pdb_data=pdb())
    assert result["status"] == "partial"
    assert result["candidates"][0]["scores"]["ddgun"]["ddg"] == 1.2
    assert result["candidates"][0]["structure_position"]["residue_number"] == 101
    assert "RuntimeError" in result["branches"]["esm"]["blocked_reason"]
    assert "private-model-environment-details" not in str(result)


@pytest.mark.asyncio
async def test_existing_mapped_structure_skips_colabfold(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    from app.tools import thermostability_adapters

    async def forbidden(*args, **kwargs):
        pytest.fail("Existing suitable structure must be reused before folding.")

    monkeypatch.setattr(thermostability_adapters, "colabfold_predict", forbidden)
    result = await thermostability_candidate_workflow(
        sequence=SEQ, objective=OBJECTIVE, identity_profile=IDENTITY,
        objective_module_plan=MODULE, mutations=["A1V"], pdb_data=pdb(), run_colabfold=True)
    assert result["branches"]["colabfold"]["status"] == "skipped"
    assert result["candidates"][0]["structure_position"]["residue_number"] == 101


@pytest.mark.asyncio
async def test_pareto_keeps_tradeoffs_without_combining_scales(monkeypatch):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    from app.tools import thermostability_adapters
    import importlib
    esm = importlib.import_module("app.tools.esm2_predict")
    monkeypatch.setattr(esm, "esm2_predict", lambda sequence, codes: esm_response(
        codes, {"A1V": 1., "D3N": 4., "E4D": 0.}))

    async def ddgun(sequence, codes):
        return {"status": "completed", "predictions": [{"mutation": code,
                "ddg": {"A1V": 4., "D3N": 1., "E4D": 0.}[code], "unit": "kcal/mol"} for code in codes]}

    monkeypatch.setattr(thermostability_adapters, "ddgun_predict", ddgun)
    result = await thermostability_candidate_workflow(
        sequence=SEQ, objective=OBJECTIVE, identity_profile=IDENTITY,
        objective_module_plan=MODULE, mutations=["E4D", "D3N", "A1V"], run_ddgun=True, run_esm=True)
    layers = {r["mutation"]: r["pareto_layer"] for r in result["candidates"]}
    assert layers == {"A1V": 1, "D3N": 1, "E4D": 2}
    assert all("composite_score" not in r for r in result["candidates"])
    assert all(r["scores"]["esm_preference"]["meaning"] == "evolutionary_preference_not_thermal_stability"
               for r in result["candidates"])


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    lambda r: r["mutations"][0].update(score=True),
    lambda r: r["mutations"][1].update(mutation="A1V"),
    lambda r: r.update(scoring_strategy="masked_marginal"),
    lambda r: r.update(is_thermostability_prediction=True),
])
async def test_esm_requires_complete_matching_candidate_set_and_truthful_strategy(monkeypatch, change):
    from app.tools.thermostability_workflow import thermostability_candidate_workflow
    import importlib
    esm = importlib.import_module("app.tools.esm2_predict")

    def predict(sequence, codes):
        response = esm_response(codes)
        change(response)
        return response

    monkeypatch.setattr(esm, "esm2_predict", predict)
    result = await thermostability_candidate_workflow(
        sequence=SEQ, objective=OBJECTIVE, identity_profile=IDENTITY,
        objective_module_plan=MODULE, mutations=["A1V", "D3N"], run_esm=True)
    assert result["status"] == "partial"
    assert all(r["scores"]["esm_preference"] is None for r in result["candidates"])


@pytest.mark.parametrize("field,value", [
    ("source_position", 1.9), ("source_position", True), ("source_position", 1.0),
    ("target_position", 101.9), ("target_position", True), ("target_position", 101.0),
])
def test_explicit_mapping_never_truncates_noninteger_coordinates(field, value):
    mapping = {"source_position": 1, "target_position": 101, "target_chain_id": "A",
               "confidence": "exact", "user_confirmed": True}
    mapping[field] = value
    result = screen(pdb_data=pdb(), mapping_rows=[mapping], mutations=["A1V"])
    assert result["status"] == "blocked"
    assert "invalid_structure_mapping" in result["blockers"]


@pytest.mark.parametrize("value", [True, 1.9, 1.0, "1.9"])
def test_functional_protection_never_truncates_noninteger_coordinates(value):
    result = screen(mutations=["A1V"], protected_sites=[{
        "position": value, "kind": "catalytic", "reference": "reviewed source"}])
    assert result["status"] == "blocked"
    assert "invalid_functional_protection" in result["blockers"]


def test_exact_integer_strings_remain_compatible_for_confirmed_mapping_and_protection():
    mapping = {"source_position": "1", "target_position": "101", "target_chain_id": "A",
               "confidence": "exact", "user_confirmed": True}
    result = screen(pdb_data=pdb(), mapping_rows=[mapping], mutations=["A1V"])
    assert result["candidates"][0]["structure_position"]["residue_number"] == 101
    result = screen(mutations=["A1V"], protected_sites=[{
        "position": "1", "kind": "catalytic", "reference": "reviewed source"}])
    assert result["candidates"] == []
    assert "catalytic" in result["rejected"][0]["reasons"]
