from __future__ import annotations

import pytest


PDB = """\
ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C
ATOM      2  NZ  LYS A   2       3.000   0.000   0.000  1.00 20.00           N
ATOM      3  CA  GLY B   1      20.000   0.000   0.000  1.00 20.00           C
HETATM    4  C1  LIG X   1       1.000   0.000   0.000  1.00 20.00           C
HETATM    5  O1  LIG X   1       1.000   2.000   0.000  1.00 20.00           O
HETATM    6  C1  LIG Y   1      20.000   0.000   0.000  1.00 20.00           C
"""


@pytest.mark.asyncio
async def test_lists_each_ligand_instance_and_residue_contacts():
    from app.tools.ligand_contact_analysis import ligand_contact_analysis

    result = await ligand_contact_analysis(pdb_data=PDB)
    assert result["status"] == "completed"
    assert result["geometry_only"] is True
    assert len(result["ligand_instances"]) == 2
    assert result["ligand_instances"][0]["instance_id"] == "LIG:X:1"
    assert result["contacts"][0]["chain_id"] == "A"
    assert result["contacts"][0]["residue_number"] == 1
    assert result["contacts"][0]["distance_angstrom"] == 1.0
    assert result["contacts"][0]["contact_type"]
    assert result["thresholds"]["contact_distance_angstrom"] == 4.5
    assert result["chain_scope"] == ["A", "B"]
    assert "binding energy" in result["interpretation_boundary"].lower()


@pytest.mark.asyncio
async def test_missing_ligand_is_not_available():
    from app.tools.ligand_contact_analysis import ligand_contact_analysis

    result = await ligand_contact_analysis(
        pdb_data="ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n"
    )
    assert result["status"] == "not_available"
    assert result["error_code"] == "NO_LIGAND"


@pytest.mark.asyncio
async def test_incomplete_coordinates_are_not_available():
    from app.tools.ligand_contact_analysis import ligand_contact_analysis

    result = await ligand_contact_analysis(pdb_data=PDB + "HETATM    7  C2  LIG X   1       BAD\n")
    assert result["status"] == "not_available"
    assert result["error_code"] == "INCOMPLETE_COORDINATES"
    assert result["coordinate_coverage"]["coverage"] < 1
