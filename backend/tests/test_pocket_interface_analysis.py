from __future__ import annotations

import pytest


PDB = """\
ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C
ATOM      2  CB  ALA A   1       0.000   1.000   0.000  1.00 20.00           C
ATOM      3  CA  GLY B   1       3.800   0.000   0.000  1.00 20.00           C
ATOM      4  CB  GLY B   1       3.800   1.000   0.000  1.00 20.00           C
HETATM    5  C1  LIG X   1       1.000   0.000   0.000  1.00 20.00           C
"""


@pytest.mark.asyncio
async def test_reports_pocket_and_chain_interface_as_geometry_only():
    from app.tools.structure_pocket_interface_analysis import structure_pocket_interface_analysis

    result = await structure_pocket_interface_analysis(pdb_data=PDB)
    assert result["status"] == "completed"
    assert result["geometry_only"] is True
    assert result["pocket"]["residues"]
    assert result["chain_interfaces"][0]["chain_ids"] == ["A", "B"]
    assert result["chain_interfaces"][0]["min_distance_angstrom"] == 3.8
    assert result["channels"]["status"] == "geometric_clues_only"
    assert "catalytic" in result["interpretation_boundary"].lower()


@pytest.mark.asyncio
async def test_no_ligand_returns_not_available_for_pocket_analysis():
    from app.tools.structure_pocket_interface_analysis import structure_pocket_interface_analysis

    result = await structure_pocket_interface_analysis(
        pdb_data="ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n"
    )
    assert result["status"] == "not_available"
    assert result["error_code"] == "NO_LIGAND"
