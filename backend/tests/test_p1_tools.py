from __future__ import annotations

import pytest

from app.tools.expression_screening import (
    host_expression_yield_predict,
    secretion_efficiency_predict,
)
from app.tools.substrate_tunnel_analysis import substrate_tunnel_analysis


SIGNAL_LIKE = "MKKLLLLLLLAVAVASAASAAP"


def test_secretion_screen_is_host_aware_and_not_overclaimed():
    result = secretion_efficiency_predict(SIGNAL_LIKE, "GS115")
    assert result["host"] == "pichia_gs115"
    assert result["status"] == "screening_only"
    assert result["predicted_secretion_efficiency"] is None
    assert 0 <= result["screening_score"] <= 1


def test_expression_yield_screen_reports_risks_not_fake_yield():
    result = host_expression_yield_predict("M" + "L" * 60, "地衣芽孢杆菌")
    assert result["host"] == "bacillus_licheniformis"
    assert result["predicted_expression_yield"] is None
    assert "multiple_hydrophobic_segments" in result["risk_factors"]

    with pytest.raises(ValueError, match="INVALID_CODING_DNA"):
        host_expression_yield_predict("MKT", "GS115", coding_dna="ATGX")


def test_tunnel_adapter_fails_closed_without_validated_engine():
    pdb = "ATOM      1  CA  ALA A   1      10.000  11.000  12.000  1.00 20.00           C"
    result = substrate_tunnel_analysis(pdb)
    assert result["status"].startswith("blocked_")
    assert result["tunnels"] == []

    with pytest.raises(ValueError, match="INVALID_PDB"):
        substrate_tunnel_analysis("not a pdb")


@pytest.mark.parametrize("engine", ["p2rank", "fpocket"])
def test_tunnel_adapter_rejects_pocket_engines(engine):
    pdb = "ATOM      1  CA  ALA A   1      10.000  11.000  12.000  1.00 20.00           C"
    result = substrate_tunnel_analysis(pdb, engine=engine)
    assert result["alternative_path"]["options"] == ["pocket_residue_lookup", "expert_structure_review"]

    assert result["status"] == "blocked_incompatible_engine"
    assert result["tunnels"] == []
