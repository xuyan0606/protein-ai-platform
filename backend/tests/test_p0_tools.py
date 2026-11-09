from __future__ import annotations

import math

import pytest

from app.tools.codon_optimize import codon_optimize
from app.tools.ph_opt_predict import ph_opt_predict
from app.tools.wetlab_result_ingest import wetlab_result_ingest


def test_codon_optimize_is_host_aware_and_auditable():
    pichia = codon_optimize("MKT", "GS115")
    bacillus = codon_optimize("MKT", "地衣芽孢杆菌")
    assert pichia["host"] == "pichia_gs115"
    assert bacillus["host"] == "bacillus_licheniformis"
    assert pichia["coding_dna"].endswith("TAA")
    assert pichia["coding_dna"] != bacillus["coding_dna"]
    assert 0 <= pichia["gc_fraction"] <= 1
    assert pichia["design_status"] == "computational_proposal"


def test_codon_optimize_rejects_unknown_host_and_amino_acids():
    with pytest.raises(ValueError, match="UNSUPPORTED_HOST"):
        codon_optimize("MKT", "E. coli")
    with pytest.raises(ValueError, match="INVALID_AA"):
        codon_optimize("MKU", "GS115")


def test_wetlab_result_ingest_is_fail_closed_and_preserves_provenance():
    record = wetlab_result_ingest(
        sample_id="mut-17",
        sequence_id="seq-1",
        metric="Tm",
        value=63.5,
        unit="°C",
        condition={"buffer": "pH 7.5"},
        replicate=2,
    )
    assert record["metric"] == "tm"
    assert record["quality"] == "unreviewed"
    assert record["training_import_allowed"] is False
    assert record["condition"]["buffer"] == "pH 7.5"

    with pytest.raises(ValueError, match="INVALID_METRIC"):
        wetlab_result_ingest("mut-17", "unknown", 1, "unit")
    with pytest.raises(ValueError, match="INVALID_VALUE"):
        wetlab_result_ingest("mut-17", "activity", math.inf, "U/mg")


def test_ph_opt_predict_is_a_guarded_screening_tool():
    result = ph_opt_predict("MDEHKR", target_residues=[2, 4])
    assert result["alternative_path"]["options"][-1] == "expert_review"
    assert result["status"] == "degraded_sequence_only"
    assert result["predicted_optimal_ph"] is None
    assert len(result["charge_titration_curve"]) == 21
    assert [item["position"] for item in result["intrinsic_residue_pka"]] == [2, 4]
    assert result["suggested_screening_ph_range"] is not None

    with pytest.raises(ValueError, match="INVALID_POSITION"):
        ph_opt_predict("MDEHKR", target_residues=[7])
