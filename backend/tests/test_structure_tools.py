"""White-box tests for residue mapping and structure search tools."""

from __future__ import annotations

import hashlib
from pathlib import Path


MINI_PDB = """\
ATOM      1  N   MET A   5      11.104  13.207  12.411  1.00 20.00           N
ATOM      2  CA  MET A   5      12.560  13.241  12.519  1.00 20.00           C
ATOM      3  C   ALA A   6      13.101  14.650  12.778  1.00 20.00           C
ATOM      4  O   ALA A   6      12.452  15.653  12.515  1.00 20.00           O
ATOM      5  N   GLY B  10      15.104  10.207  11.411  1.00 20.00           N
ATOM      6  CA  GLY B  10      16.560  10.241  11.519  1.00 20.00           C
END
"""

COMPLEX_PDB = """\
ATOM      1  CA  ALA A  -3       0.000   0.000   0.000  1.00 15.00           C
ATOM      2  CA  GLU A 109       3.800   0.000   0.000  1.00 15.00           C
HETATM    3  C1  XYP B   1       1.000   0.000   0.000  1.00 15.00           C
HETATM    4  C2  XYP B   1       1.500   0.000   0.000  1.00 15.00           C
HETATM    5  C1  XYP C   1       2.000   0.000   0.000  1.00 15.00           C
END
"""


async def test_disulfide_saltbridge_scan_uses_first_model_and_separates_histidine():
    from app.tools.disulfide_saltbridge_scan import disulfide_saltbridge_scan

    def atom(serial, atom_name, residue, number, x, y, z):
        return (f"ATOM  {serial:5d} {atom_name:<4s} {residue:>3s} A{number:4d}    "
                f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{20.0:6.2f}          {atom_name[0]:>2s}\n")

    pdb = ("MODEL        1\n"
           + atom(1, 'SG', 'CYS', 2, 0, 0, 0)
           + atom(2, 'SG', 'CYS', 8, 2.02, 0, 0)
           + atom(3, 'NZ', 'LYS', 3, 0, 5, 0)
           + atom(4, 'OD1', 'ASP', 6, 0, 8, 0)
           + atom(5, 'ND1', 'HIS', 10, 0, 11, 0)
           + 'ENDMDL\nMODEL        2\n'
           + atom(6, 'SG', 'CYS', 2, 0, 0, 0)
           + atom(7, 'SG', 'CYS', 8, 12, 0, 0)
           + 'ENDMDL\n')
    result = await disulfide_saltbridge_scan(pdb_data=pdb, chain_id='A')
    assert result['status'] == 'completed'
    assert result['residue_count'] == 5
    assert result['disulfide_bonds'][0]['sg_distance_angstrom'] == 2.02
    assert result['salt_bridges'][0]['distance_angstrom'] == 3.0
    assert result['histidine_acidic_contacts'][0]['residue_1'] == 'A:10'


class TestResidueMappingSifts:
    def test_pocket_author_number_is_projected_to_input_sequence_position(self):
        from app.core.agent_graph import AgentOrchestrator, PlanStep

        step = PlanStep(2, "mutation_priority_score", "rank", {"sequence": "AAAA", "engineering_goal": "activity"})
        completed = [
            PlanStep(1, "residue_mapping_sifts", "map", {}, "completed", {
                "numbering_registry_rows": [{
                    "target_scheme": "pdb_author", "target_position": 109,
                    "target_chain_id": "A", "source_scheme": "user_sequence",
                    "source_position": 2, "target_insertion_code": None,
                }]
            }),
            PlanStep(1, "pocket_residue_lookup", "pocket", {}, "completed", {
                "residue_positions": [{"chain_id": "A", "pdb_residue_no": 109, "pocket_id": "pocket1"}]
            }),
        ]
        bridged = AgentOrchestrator()._bridge_step_params(step, completed)
        assert bridged.params["pocket_residue_positions"][0]["user_sequence_position"] == 2
        assert bridged.params["pocket_residue_positions"][0]["mapping_source"] == "residue_mapping_sifts"

    def test_fpocket_atom_parser_returns_unique_author_residues(self, tmp_path):
        from app.tools.pocket_residue_lookup import _parse_fpocket_atoms

        path = tmp_path / "pocket1_atm.pdb"
        path.write_text(
            "ATOM      1  CA  ALA A  10       0.000   0.000   0.000  1.00 20.00           C\n"
            "ATOM      2  CB  ALA A  10       0.000   0.000   0.000  1.00 20.00           C\n"
            "ATOM      3  CA  GLY B  12       0.000   0.000   0.000  1.00 20.00           C\n"
        )
        rows = _parse_fpocket_atoms(path, "A")
        assert [(row["chain_id"], row["pdb_residue_no"]) for row in rows] == [("A", 10), ("B", 12)]
        assert all(row["source"] == "fpocket" for row in rows)

    def test_pocket_runtime_can_be_configured_by_binary_environment(self, monkeypatch, tmp_path):
        from app.tools.pocket_residue_lookup import _resolve_executable

        binary = tmp_path / "p2rank"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)
        monkeypatch.setenv("P2RANK_BINARY", str(binary))
        assert _resolve_executable("p2rank") == str(binary)

    async def test_pocket_residue_lookup_is_runtime_gated_and_never_fabricates_sites(self, monkeypatch):
        import app.tools.pocket_residue_lookup as pocket_module

        monkeypatch.setattr(pocket_module.shutil, "which", lambda _: None)
        result = await pocket_module.pocket_residue_lookup(pdb_data=COMPLEX_PDB)
        assert result["status"] == "blocked"
        assert result["error_code"] == "RUNTIME_UNAVAILABLE"
        assert result["residue_positions"] == []
        assert result["capability_status"] == "real_runtime_gated"

    async def test_excludes_nonpolymer_ligand_chains_and_verifies_exact_sequence_mapping(self):
        from app.services.pdb_parser import parse_pdb
        from app.tools.residue_mapping_sifts import residue_mapping_sifts

        parsed = parse_pdb(COMPLEX_PDB)
        assert [chain["chain_id"] for chain in parsed["chains"]] == ["A"]
        assert parsed["total_residues"] == 2
        assert parsed["nonpolymer_components"] == [
            {"component_id": "XYP", "chain_id": "B", "residue_number": 1, "insertion_code": None, "atom_count": 2},
            {"component_id": "XYP", "chain_id": "C", "residue_number": 1, "insertion_code": None, "atom_count": 1},
        ]

        result = await residue_mapping_sifts(
            pdb_data=COMPLEX_PDB,
            pdb_id="3WP6",
            chain_id="A",
            input_sequence="AE",
        )
        assert result["source"] == "input_sequence_exact_coordinate_mapping"
        assert result["mapping_count"] == 2
        assert result["numbering_registry_status"] == "ready"
        assert result["mappings"][1]["pdb_residue_no"] == 109

    def test_direct_query_structure_evidence_identifies_family_and_protects_construct_site(self):
        from app.tools.enzyme_identity_profile import enzyme_identity_profile

        sequence = "A" * 12
        mapping_rows = [
            {
                "source_scheme": "user_sequence",
                "source_position": 10,
                "target_position": 109,
                "target_residue_aa": "A",
                "confidence": "exact",
            }
        ]
        result = enzyme_identity_profile(
            sequence=sequence,
            structure_id="3WP6",
            residue_mapping={"numbering_registry_status": "ready", "numbering_registry_rows": mapping_rows},
            structure_evidence={
                "query_rcsb_annotation": {
                    "status": "completed",
                    "hits": [{
                        "pdb_id": "3WP6",
                        "title": "THE COMPLEX STRUCTURE OF CDBFV E109A WITH XYLOTRIOSE",
                        "entity_description": "CDBFV beta-xylanase",
                        "nonpolymer_entities": [{"component_id": "XYP", "name": "XYLOTRIOSE"}],
                    }],
                }
            },
        )
        assert result["identity_status"] == "identified"
        assert result["guardrail"]["status"] == "ready"
        assert 10 in result["protected_positions"]
        assert result["structure_ligands"][0]["component_id"] == "XYP"

    def test_uniprot_only_mapping_does_not_verify_input_sequence_numbering(self):
        from app.tools.enzyme_identity_profile import enzyme_identity_profile

        result = enzyme_identity_profile(
            sequence="A" * 12,
            residue_mapping={
                "numbering_registry_status": "uniprot_only_requires_input_alignment",
                "numbering_registry_rows": [{
                    "source_scheme": "uniprot", "source_position": 205,
                    "target_scheme": "pdb_author", "target_position": 5,
                }],
            },
        )

        assert result["numbering"]["status"] != "verified_for_input_sequence"
        assert result["guardrail"]["status"] == "blocked"

    async def test_maps_chain_with_uniprot_offset(self):
        from app.tools.residue_mapping_sifts import residue_mapping_sifts

        result = await residue_mapping_sifts(
            pdb_data=MINI_PDB,
            chain_id="A",
            uniprot_id="PTEST1",
            uniprot_start=101,
        )

        assert result["found"] is True
        assert result["capability_status"] == "coordinate_order_inference"
        assert result["evidence_level"] == "COORDINATE_ORDER_INFERENCE"
        assert "不是外部 SIFTS/UniProt 实证映射" in result["report_boundary"]
        assert result["mapping_count"] == 2
        assert result["mappings"][0]["pdb_residue_no"] == 5
        assert result["mappings"][0]["uniprot_position"] is None
        assert result["mappings"][0]["coordinate_sequence_position"] == 1
        assert result["mappings"][1]["residue_aa"] == "A"
        assert result["numbering_registry_status"] == "inferred_requires_confirmation"
        assert result["coordinate_systems"] == ["coordinate_sequence", "pdb_author"]
        assert result["numbering_registry_rows"][0]["source_scheme"] == "coordinate_sequence"
        assert result["numbering_registry_rows"][0]["source_position"] == 1
        assert result["numbering_registry_rows"][0]["target_scheme"] == "pdb_author"
        assert result["numbering_registry_rows"][0]["target_position"] == 5
        assert result["numbering_registry_rows"][0]["confidence"] == "inferred"

    async def test_mismatched_input_sequence_blocks_mapping(self):
        from app.tools.residue_mapping_sifts import residue_mapping_sifts

        result = await residue_mapping_sifts(
            pdb_data=MINI_PDB, chain_id="A", input_sequence="MAA"
        )

        assert result["status"] == "blocked"
        assert result["error_code"] == "INPUT_SEQUENCE_MISMATCH"
        assert result["mapping_count"] == 0
        assert result["mappings"] == []
        assert result["numbering_registry_rows"] == []

    async def test_missing_pdb_returns_error_contract(self):
        from app.tools.residue_mapping_sifts import residue_mapping_sifts

        result = await residue_mapping_sifts()

        assert result["found"] is False
        assert result["error_code"] == "MISSING_PDB"

    async def test_prefers_local_sifts_mapping_file(self, monkeypatch, tmp_path):
        from app.core.config import settings
        from app.tools.residue_mapping_sifts import residue_mapping_sifts

        mapping_dir = tmp_path / "sifts"
        mapping_dir.mkdir()
        (mapping_dir / "1abc.json").write_text(
            """
            {
              "mappings": [
                {
                  "pdb_id": "1abc",
                  "chain_id": "A",
                  "pdb_residue_no": 5,
                  "residue_name": "MET",
                  "uniprot_id": "PTEST1",
                  "uniprot_position": 205
                }
              ]
            }
            """,
            encoding="utf-8",
        )
        monkeypatch.setattr(settings, "SIFTS_MAPPING_PATH", str(mapping_dir), raising=False)

        result = await residue_mapping_sifts(
            pdb_data=MINI_PDB,
            pdb_id="1abc",
            chain_id="A",
            uniprot_id="PTEST1",
            uniprot_start=101,
        )

        assert result["found"] is True
        assert result["source"] == "local_sifts_mapping"
        assert result["capability_status"] == "local_residue_mapping"
        assert result["evidence_level"] == "NUMBERING_MAPPING"
        assert "核对来源、链、缺失残基" in result["report_boundary"]
        assert result["mapping_count"] == 1
        assert result["mappings"][0]["uniprot_position"] == 205
        assert result["numbering_registry_status"] == "uniprot_only_requires_input_alignment"
        assert result["numbering_registry_rows"][0]["source_scheme"] == "uniprot"
        assert result["numbering_registry_rows"][0]["source_position"] == 205
        assert result["numbering_registry_rows"][0]["target_scheme"] == "pdb_author"
        assert result["numbering_registry_rows"][0]["target_position"] == 5
        assert result["numbering_registry_rows"][0]["confidence"] == "sifts"
        assert result["coordinate_systems"] == ["uniprot", "pdb_author"]
        assert result["limitations"] == []

    async def test_local_sifts_row_with_wrong_residue_is_blocked(self, monkeypatch, tmp_path):
        from app.core.config import settings
        from app.tools.residue_mapping_sifts import residue_mapping_sifts

        mapping_file = tmp_path / "1abc.csv"
        mapping_file.write_text(
            "pdb_id,chain_id,pdb_residue_no,residue_aa,uniprot_id,uniprot_position\n"
            "1abc,A,5,G,PTEST1,205\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(settings, "SIFTS_MAPPING_PATH", str(mapping_file), raising=False)

        result = await residue_mapping_sifts(
            pdb_data=MINI_PDB, pdb_id="1abc", chain_id="A", uniprot_id="PTEST1"
        )

        assert result["status"] == "blocked"
        assert result["error_code"] == "LOCAL_MAPPING_COORDINATE_MISMATCH"
        assert result["numbering_registry_rows"] == []


class TestStructureSearchFoldseek:
    def test_multiline_title_and_seqres_are_preserved_per_chain(self):
        from app.tools.structure_search_foldseek import _structure_summary

        pdb = "\n".join([
            "TITLE     STRUCTURE OF BETA-MANNANASE",
            "TITLE    2 WITH MANNOBIOSE",
            "SEQRES   1 A    2  ALA ASN",
            "SEQRES   1 B    3  GLY LEU VAL",
            "ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00 20.00           C",
            "ATOM      2  CA  GLY B   1      11.000  10.000  10.000  1.00 20.00           C",
            "END",
        ])
        summary = _structure_summary(pdb)

        assert summary["title"] == "STRUCTURE OF BETA-MANNANASE WITH MANNOBIOSE"
        assert summary["seqres_by_chain"] == {"A": 2, "B": 3}

    def test_structure_summary_preserves_direct_pdb_construct_annotations(self):
        from app.tools.structure_search_foldseek import _structure_summary

        pdb = "\n".join([
            "HEADER    HYDROLASE                               07-JAN-98   1BLI",
            "COMPND    MOL_ID: 1;",
            "COMPND   2 MOLECULE: ALPHA-AMYLASE;",
            "COMPND   3 EC: 3.2.1.1;",
            "COMPND   4 ENGINEERED: YES;",
            "SEQADV 1BLI PHE A  190  UNP  P06278    ASN   219 ENGINEERED MUTATION",
            "SEQRES   1 A    3  ALA ASN LEU",
            "ATOM      1  CA  ASN A   2      10.000  10.000  10.000  1.00 20.00           C",
            "ATOM      2  CA  LEU A   3      11.000  10.000  10.000  1.00 20.00           C",
            "END",
        ])
        summary = _structure_summary(pdb)

        assert summary["total_residues"] == 2
        assert summary["seqres_length"] == 3
        assert summary["compound_annotation"]["molecule"] == "ALPHA-AMYLASE"
        assert summary["compound_annotation"]["ec"] == "3.2.1.1"
        assert summary["compound_annotation"]["engineered"] == "YES"
        assert summary["engineered_mutations"] == [
            {"chain_id": "A", "pdb_residue_no": 190, "pdb_residue_aa": "PHE",
             "reference_residue_aa": "ASN", "reference_position": 219}
        ]

    def test_multiple_compound_entities_do_not_become_one_identity(self):
        from app.services.pdb_parser import parse_pdb

        parsed = parse_pdb("\n".join([
            "COMPND    MOL_ID: 1;",
            "COMPND   2 MOLECULE: ALPHA-AMYLASE;",
            "COMPND   3 MOL_ID: 2;",
            "COMPND   4 MOLECULE: OTHER PROTEIN;",
            "END",
        ]))

        assert parsed["compound_annotation"] == {}

    async def test_cache_key_distinguishes_structures_with_same_prefix(self, monkeypatch):
        from app.core.config import settings
        from app.tools import structure_search_foldseek as module

        cache_params = []

        async def fake_get_cached_result(_tool, params, **_kwargs):
            cache_params.append(params)
            return None

        monkeypatch.setattr(module, "get_cached_result", fake_get_cached_result)
        monkeypatch.setattr(settings, "FOLDSEEK_API_URL", "", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_BINARY", "", raising=False)
        prefix = "HEADER    TEST\n" + "REMARK    " + "X" * 2100 + "\n"
        for residue in ("ALA", "GLY"):
            await module.structure_search_foldseek(
                pdb_data=prefix + f"ATOM      1  CA  {residue} A   1      11.104  13.207  12.411  1.00 20.00           C\nEND\n"
            )

        assert len(cache_params) >= 2
        assert cache_params[0]["pdb_sha256"] != cache_params[1]["pdb_sha256"]

    async def test_foldseek_without_endpoint_returns_degraded_summary(self, monkeypatch):
        from app.core.config import settings
        from app.tools.structure_search_foldseek import structure_search_foldseek

        monkeypatch.setattr(settings, "FOLDSEEK_API_URL", "", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_BINARY", "", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_DATABASE_PDB", "", raising=False)

        result = await structure_search_foldseek(pdb_data=MINI_PDB, max_results=5)

        assert result["found"] is False
        assert result["status"] == "degraded"
        assert result["error_code"] == "FOLDSEEK_NOT_CONFIGURED"
        assert result["backend"] == "summary_only"
        assert result["capability_status"] == "structure_input_qc"
        assert result["evidence_level"] == "STRUCTURE_INPUT_QC"
        assert "不能单独确认" in result["report_boundary"]
        assert result["query_structure"]["chain_count"] == 2
        assert result["query_structure"]["total_residues"] == 3
        assert result["query_structure"]["chains"][0]["sequence_sha256"] == hashlib.sha256(b"MA").hexdigest()

    async def test_foldseek_local_cli_returns_hits(self, monkeypatch, tmp_path):
        from app.core.config import settings
        from app.tools import structure_search_foldseek as module

        db_path = tmp_path / "foldseek-db"
        db_path.mkdir()

        def fake_execute_local_foldseek_command(
            *,
            binary: str,
            query_path: Path,
            database_path: str,
            result_path: Path,
            work_dir: Path,
            max_results: int,
        ) -> None:
            assert binary == "foldseek"
            assert query_path.exists()
            assert database_path == str(db_path)
            assert max_results == 3
            work_dir.mkdir(parents=True, exist_ok=True)
            result_path.write_text(
                "query\t8abc_A\t1e-20\t120.5\t0.81\t0.79\t0.84\t0.97\n",
                encoding="utf-8",
            )

        monkeypatch.setattr(settings, "FOLDSEEK_API_URL", "", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_BINARY", "foldseek", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_DATABASE_PDB", str(db_path), raising=False)
        monkeypatch.setattr(module, "_execute_local_foldseek_command", fake_execute_local_foldseek_command)

        result = await module.structure_search_foldseek(
            pdb_data=MINI_PDB,
            database="pdb",
            max_results=3,
        )

        assert result["found"] is True
        assert result["status"] == "completed"
        assert result["backend"] == "local_cli"
        assert result["capability_status"] == "structure_similarity_search"
        assert result["evidence_level"] == "STRUCTURE_SIMILARITY"
        assert "弱 TM-score" in result["report_boundary"]
        assert result["database_path"] == str(db_path)
        assert result["results_count"] == 1
        assert result["results"][0]["target"] == "8abc_A"
        assert result["results"][0]["aligned_tm_score"] == 0.81

    async def test_foldseek_root_directory_resolves_db_prefix(self, monkeypatch, tmp_path):
        from app.core.config import settings
        from app.tools import structure_search_foldseek as module

        db_root = tmp_path / "foldseek-root"
        db_dir = db_root / "pdb"
        db_dir.mkdir(parents=True)
        (db_dir / "protein_ai_pdb").write_text("stub", encoding="utf-8")
        (db_dir / "protein_ai_pdb.dbtype").write_text("stub", encoding="utf-8")
        (db_dir / "protein_ai_pdb.index").write_text("stub", encoding="utf-8")
        (db_dir / "protein_ai_pdb.lookup").write_text("stub", encoding="utf-8")
        (db_dir / "protein_ai_pdb_ca.dbtype").write_text("stub", encoding="utf-8")

        def fake_execute_local_foldseek_command(
            *,
            binary: str,
            query_path: Path,
            database_path: str,
            result_path: Path,
            work_dir: Path,
            max_results: int,
        ) -> None:
            assert database_path == str(db_dir / "protein_ai_pdb")
            work_dir.mkdir(parents=True, exist_ok=True)
            result_path.write_text(
                "query\t8abc_A\t1e-20\t120.5\t0.81\t0.79\t0.84\t0.97\n",
                encoding="utf-8",
            )

        monkeypatch.setattr(settings, "FOLDSEEK_API_URL", "", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_BINARY", "foldseek", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_DATABASE_PDB", "", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_DATABASE_ROOT", str(db_root), raising=False)
        monkeypatch.setattr(module, "_execute_local_foldseek_command", fake_execute_local_foldseek_command)

        result = await module.structure_search_foldseek(
            pdb_data=MINI_PDB,
            database="pdb",
            max_results=3,
        )

        assert result["found"] is True
        assert result["database_path"] == str(db_dir / "protein_ai_pdb")

    async def test_structure_tools_registered(self):
        from app.tools.registry import ToolRegistry

        ToolRegistry.discover()

        mapping_tool = ToolRegistry.get_tool("residue_mapping_sifts")
        search_tool = ToolRegistry.get_tool("structure_search_foldseek")

        assert mapping_tool is not None
        assert mapping_tool.category == "structure"
        assert search_tool is not None
        assert search_tool.category == "structure"


SITE_FEATURE_PDB = """\
HELIX    1   1 MET A    5  ASP A    6  1                                   2
SHEET    1   A 1 SER A   8  GLY A   9  0
ATOM      1  N   MET A   5       0.000   1.000   0.000  1.00 21.00           N
ATOM      2  CA  MET A   5       0.000   0.000   0.000  1.00 20.00           C
ATOM      3  C   MET A   5       1.200   0.000   0.000  1.00 22.00           C
ATOM      4  N   ASP A   6       3.500   1.000   0.000  1.00 31.00           N
ATOM      5  CA  ASP A   6       4.000   0.000   0.000  1.00 30.00           C
ATOM      6  C   ASP A   6       5.200   0.000   0.000  1.00 32.00           C
ATOM      7  N   SER A   8       8.500   1.000   0.000  1.00 71.00           N
ATOM      8  CA  SER A   8       9.000   0.000   0.000  1.00 70.00           C
ATOM      9  N   GLY A   9      20.000   1.000   0.000  1.00 41.00           N
ATOM     10  C   GLY A   9      21.000   1.000   0.000  1.00 42.00           C
ATOM     11  CA  GLY B   5       0.000  10.000   0.000  1.00 20.00           C
HETATM   12  C1  NAG A 201       0.000   0.000   3.000  1.00 20.00           C
HETATM   13  O   HOH A 301       0.000   0.000   1.000  1.00 20.00           O
END
"""

MULTI_MODEL_SITE_FEATURE_PDB = """\
MODEL        1
ATOM      1  N   MET A   5       0.000   1.000   0.000  1.00 21.00           N
ATOM      2  CA  MET A   5       0.000   0.000   0.000  1.00 20.00           C
ATOM      3  C   MET A   5       1.200   0.000   0.000  1.00 22.00           C
HETATM    4  C1  NAG A 201       0.000   0.000   3.000  1.00 20.00           C
ENDMDL
MODEL        2
ATOM      5  N   MET A   5      50.000   1.000   0.000  1.00 21.00           N
ATOM      6  CA  MET A   5      50.000   0.000   0.000  1.00 20.00           C
ATOM      7  C   MET A   5      51.200   0.000   0.000  1.00 22.00           C
HETATM    8  C1  NAG A 201      60.000   0.000   0.000  1.00 20.00           C
ENDMDL
END
"""

TORSION_PDB = """\
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00 20.00           C
ATOM      3  C   ALA A   1       1.000   1.000   0.000  1.00 20.00           C
ATOM      4  N   GLY A   2       2.300   1.000   0.000  1.00 20.00           N
ATOM      5  CA  GLY A   2       3.300   1.000   1.000  1.00 20.00           C
ATOM      6  C   GLY A   2       3.300   2.000   1.000  1.00 20.00           C
ATOM      7  N   SER A   3       4.600   2.000   1.000  1.00 20.00           N
ATOM      8  CA  SER A   3       5.600   2.000   0.000  1.00 20.00           C
ATOM      9  C   SER A   3       5.600   3.000   0.000  1.00 20.00           C
END
"""

TORSION_GAP_PDB = """\
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00           N
ATOM      2  CA  ALA A   1       1.000   0.000   0.000  1.00 20.00           C
ATOM      3  C   ALA A   1       1.000   1.000   0.000  1.00 20.00           C
ATOM      4  N   GLY A   2      10.000   1.000   0.000  1.00 20.00           N
ATOM      5  CA  GLY A   2      11.000   1.000   1.000  1.00 20.00           C
ATOM      6  C   GLY A   2      11.000   2.000   1.000  1.00 20.00           C
ATOM      7  CA  SER A   3      12.000   2.000   0.000  1.00 20.00           C
ATOM      8  C   SER A   3      12.000   3.000   0.000  1.00 20.00           C
END
"""


class TestSiteStructureFunctionFeatures:
    async def test_real_mmcif_residue_mapping_and_site_features(self):
        from app.tools.residue_mapping_sifts import residue_mapping_sifts
        from app.tools.site_structure_function_features import build_site_structure_function_features

        cif = (Path(__file__).resolve().parent / "fixtures/4HHB.cif").read_text(encoding="utf-8")
        mapping = await residue_mapping_sifts(pdb_data=cif, pdb_id="4HHB", chain_id="A")
        assert mapping["status"] == "completed"
        assert mapping["mapping_count"] == 141
        assert mapping["source"] == "local_sifts_style_inference"

        features = await build_site_structure_function_features(
            pdb_data=cif, chain_id="A", residue_mappings=mapping["mappings"]
        )
        assert features["status"] == "completed"
        assert len(features["features"]) == 141
        assert any(row["has_ca"] for row in features["features"])

    async def test_builds_ca_distance_contact_and_mapping_features(self):
        from app.tools.site_structure_function_features import build_site_structure_function_features

        result = await build_site_structure_function_features(
            pdb_data=SITE_FEATURE_PDB,
            chain_id="A",
            catalytic_positions=[106],
            protected_positions=[106],
            residue_mappings=[
                {
                    "chain_id": "A",
                    "pdb_residue_no": 5,
                    "residue_aa": "M",
                    "uniprot_position": 105,
                    "mapping_confidence": "curated_sifts",
                },
                {
                    "chain_id": "A",
                    "pdb_residue_no": 6,
                    "residue_aa": "D",
                    "uniprot_position": 106,
                    "mapping_confidence": "curated_sifts",
                },
                {
                    "chain_id": "A",
                    "pdb_residue_no": 8,
                    "residue_aa": "S",
                    "uniprot_position": 108,
                    "mapping_confidence": "curated_sifts",
                },
            ],
        )

        assert result["found"] is True
        assert result["status"] == "completed"
        assert result["schema_version"] == "site_structure_function_features_v1"
        assert result["capability_status"] == "structure_feature_table"
        assert result["evidence_level"] == "STRUCTURE_GEOMETRY_FEATURES"
        assert "不能单独证明酶身份" in result["report_boundary"]
        assert "B-factor 仅保留为 PDB 原始字段" in result["report_boundary"]
        assert result["feature_table_contract"]["schema_version"] == "site_structure_function_features_contract_v1"
        assert result["feature_table_contract"]["status"] == "ready"
        assert result["feature_table_contract"]["field_state"]["residue_distance_graph"] == "ready"
        assert result["feature_table_contract"]["field_state"]["pocket_channel_interface"] == "not_computed"
        assert "pocket_channel_interface_assignment" in result["feature_table_contract"]["must_not_claim"]
        assert result["feature_count"] == 4
        assert result["summary"]["mapped_count"] == 3
        assert result["summary"]["ca_available_count"] == 3
        assert result["summary"]["secondary_structure_source"] == "pdb_helix_sheet_records"
        assert result["summary"]["rel_sasa_status"] == "computed"
        assert result["summary"]["nonpolymer_proximity_status"] == "computed_from_input_pdb"
        assert result["summary"]["nonpolymer_component_count"] == 1
        assert result["summary"]["nonpolymer_heavy_atom_count"] == 1
        assert result["summary"]["nonpolymer_component_ids"] == ["NAG"]
        assert result["summary"]["distance_graph_status"] == "ready"
        assert result["summary"]["distance_graph_node_count"] == 3
        assert result["summary"]["distance_graph_edge_count"] == 2
        assert result["residue_distance_graph"]["schema_version"] == "residue_distance_graph_v1"
        assert result["residue_distance_graph"]["coordinate_basis"] == "ca_atom"
        assert "not a pocket" in result["residue_distance_graph"]["boundary"]
        assert {
            (edge["source_position"], edge["target_position"], edge["distance_ca_angstrom"])
            for edge in result["residue_distance_graph"]["edges"]
        } == {(105, 106, 4.0), (106, 108, 5.0)}

        met = next(row for row in result["features"] if row["position"] == 105)
        assert met["wild_type"] == "M"
        assert met["pdb_position"] == "A:5"
        assert met["pdb_author_coordinate"] == {
            "chain_id": "A",
            "residue_no": 5,
            "insertion_code": None,
        }
        assert met["user_sequence_coordinate"] == {"position": 105, "status": "verified"}
        assert met["uniprot_coordinate"] == {
            "accession": None,
            "position": 105,
            "status": "verified",
        }
        assert met["projection_eligibility"] == {
            "user_sequence": True,
            "uniprot": True,
            "reason": "verified_one_to_one_mapping",
        }
        assert met["ca_coord"] == {"x": 0.0, "y": 0.0, "z": 0.0}
        assert met["b_factor"] == 20.0
        assert met["secondary_structure"] == "helix"
        assert met["secondary_structure_source"] == "pdb_helix_sheet_records"
        assert met["rel_sasa_status"] == "computed_from_input_pdb"
        assert isinstance(met["rel_sasa"], float)
        assert 0.0 <= met["rel_sasa"] <= 1.5
        assert met["rel_sasa_source"] == "biopython_shrake_rupley_tien_max_asa"
        assert met["pocket_channel_interface_status"] == "not_computed"
        assert met["nonpolymer_proximity_status"] == "computed_from_input_pdb"
        assert met["nearest_nonpolymer_heteroatom_distance_angstrom"] == 3.0
        assert met["nearest_nonpolymer_component_id"] == "NAG"
        assert met["nearest_nonpolymer_component_position"] == "A:201"
        assert met["nonpolymer_component_ids_within_4a"] == ["NAG"]
        assert "within_4A_of_nonpolymer_heteroatom_review_component_role" in met["risk_flags"]
        assert met["nearest_catalytic_position"] == 106
        assert met["nearest_catalytic_distance_ca_angstrom"] == 4.0
        assert met["nearest_ca_neighbor_position"] == 106
        assert met["nearest_ca_neighbor_distance_angstrom"] == 4.0
        assert met["contact_count_ca_8a"] == 1
        assert met["ca_contact_environment"] == "sparse_ca_neighborhood"

        catalytic = next(row for row in result["features"] if row["position"] == 106)
        assert catalytic["is_catalytic"] is True
        assert catalytic["is_protected"] is True
        assert catalytic["contact_count_ca_8a"] == 2
        assert "protected_or_catalytic_position" in catalytic["risk_flags"]

        high_b = next(row for row in result["features"] if row["position"] == 108)
        assert high_b["secondary_structure"] == "sheet"
        assert high_b["b_factor"] == 70.0
        assert "high_ca_b_factor_review_structure_quality" not in high_b["risk_flags"]
        assert result["summary"]["b_factor_interpretation"] == "raw_source_dependent_field_not_a_thermostability_measure"

        missing_ca = next(row for row in result["features"] if row["pdb_residue_no"] == 9)
        assert missing_ca["has_ca"] is False
        assert missing_ca["nearest_ca_neighbor_position"] is None
        assert missing_ca["contact_count_ca_8a"] == 0
        assert missing_ca["ca_contact_environment"] == "missing_ca_coordinate"
        assert "missing_ca_coordinate" in missing_ca["risk_flags"]

    async def test_computes_backbone_phi_psi_and_marks_terminal_residues(self):
        from app.tools.site_structure_function_features import build_site_structure_function_features

        result = await build_site_structure_function_features(pdb_data=TORSION_PDB, chain_id="A")

        assert result["summary"]["backbone_torsion_status"] == "computed"
        first, middle, last = result["features"]
        assert first["backbone_torsion_status"] == "partial"
        assert first["phi_deg"] is None
        assert abs(first["psi_deg"]) == 180.0
        assert middle["backbone_torsion_status"] == "computed"
        assert middle["phi_deg"] == -90.0
        assert middle["psi_deg"] == -135.0
        assert middle["backbone_torsion_reason"] is None
        assert last["backbone_torsion_status"] == "partial"
        assert last["phi_deg"] == 90.0
        assert last["psi_deg"] is None
        assert last["backbone_torsion_source"] == "input_pdb_backbone_atoms_first_model"

    def test_dihedral_matches_independent_biopython_convention(self):
        from math import degrees
        from Bio.PDB.vectors import Vector, calc_dihedral
        from app.tools.site_structure_function_features import _dihedral_degrees

        # Reference coordinate quartets from real 1CRN: psi(1), phi(7).
        quartets = [
            ((17.047, 14.099, 3.625), (16.967, 12.784, 4.338),
             (15.685, 12.755, 5.133), (15.115, 11.555, 5.265)),
            ((8.753, 4.376, 14.083), (8.881, 3.075, 14.358),
             (8.912, 2.083, 13.258), (7.581, 2.090, 12.506)),
            ((0, 0, 1), (0, 0, 0), (1, 0, 0), (1, 1, 0)),
            ((0, 0, -1), (0, 0, 0), (1, 0, 0), (1, 1, 0)),
        ]
        for quartet in quartets:
            expected = degrees(calc_dihedral(*(Vector(*point) for point in quartet)))
            actual = _dihedral_degrees(*quartet)
            circular_error = abs((actual - expected + 180) % 360 - 180)
            assert circular_error < 0.01, (quartet, actual, expected)

        assert _dihedral_degrees(*quartets[0]) == 147.66
        assert _dihedral_degrees(*quartets[1]) == -63.58
        assert abs(_dihedral_degrees((0, 0, 0), (1, 0, 0), (1, 1, 0), (2, 1, 0))) == 180
        assert _dihedral_degrees((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)) == 0
        assert _dihedral_degrees((0, 0, 0), (0, 0, 0), (1, 0, 0), (1, 1, 0)) is None
        assert _dihedral_degrees((0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0)) is None

    async def test_marks_missing_backbone_atoms_and_peptide_breaks_without_interpolation(self):
        from app.tools.site_structure_function_features import build_site_structure_function_features

        result = await build_site_structure_function_features(pdb_data=TORSION_GAP_PDB, chain_id="A")

        middle = next(row for row in result["features"] if row["pdb_residue_no"] == 2)
        last = next(row for row in result["features"] if row["pdb_residue_no"] == 3)
        assert middle["backbone_torsion_status"] == "not_computed"
        assert "peptide_chain_break_before_residue" in middle["backbone_torsion_reason"]
        assert "missing_backbone_atom_for_psi" in middle["backbone_torsion_reason"]
        assert last["backbone_torsion_status"] == "not_computed"
        assert "missing_backbone_atom_for_phi" in last["backbone_torsion_reason"]

    async def test_uses_only_first_model_for_geometry_and_nonpolymer_contacts(self):
        from app.tools.site_structure_function_features import build_site_structure_function_features

        result = await build_site_structure_function_features(
            pdb_data=MULTI_MODEL_SITE_FEATURE_PDB,
            chain_id="A",
        )

        assert result["feature_count"] == 1
        row = result["features"][0]
        assert row["ca_coord"] == {"x": 0.0, "y": 0.0, "z": 0.0}
        assert row["nearest_nonpolymer_heteroatom_distance_angstrom"] == 3.0
        assert row["nearest_nonpolymer_component_position"] == "A:201"

    async def test_filters_target_positions_across_mapping_and_pdb_numbering(self):
        from app.tools.site_structure_function_features import build_site_structure_function_features

        result = await build_site_structure_function_features(
            pdb_data=SITE_FEATURE_PDB,
            chain_id="A",
            target_positions=[105, 9],
            residue_mappings=[
                {
                    "chain_id": "A",
                    "pdb_residue_no": 5,
                    "uniprot_position": 105,
                    "mapping_confidence": "curated_sifts",
                }
            ],
        )

        positions = {row["position"] for row in result["features"]}
        pdb_numbers = {row["pdb_residue_no"] for row in result["features"]}
        assert positions == {105, 9}
        assert pdb_numbers == {5, 9}

    async def test_inferred_mapping_keeps_geometry_but_blocks_projection(self):
        from app.tools.site_structure_function_features import build_site_structure_function_features

        result = await build_site_structure_function_features(
            pdb_data=SITE_FEATURE_PDB,
            chain_id="A",
            catalytic_positions=[105],
            residue_mappings=[
                {
                    "chain_id": "A",
                    "pdb_residue_no": 5,
                    "uniprot_position": 105,
                    "mapping_confidence": "inferred_from_coordinate_order",
                }
            ],
        )

        row = next(item for item in result["features"] if item["pdb_residue_no"] == 5)
        assert row["has_ca"] is True
        assert row["ca_coord"] == {"x": 0.0, "y": 0.0, "z": 0.0}
        assert row["user_sequence_coordinate"] == {
            "position": 105,
            "status": "inferred_requires_confirmation",
        }
        assert row["uniprot_coordinate"] == {
            "accession": None,
            "position": 105,
            "status": "inferred_requires_confirmation",
        }
        assert row["projection_eligibility"]["user_sequence"] is False
        assert row["projection_eligibility"]["uniprot"] is False
        assert row["projection_eligibility"]["reason"] == "inferred_mapping_requires_confirmation"
        assert row["is_catalytic"] is False
        assert result["summary"]["inferred_mapping_count"] == 1

    async def test_chain_and_insertion_code_form_stable_residue_identity(self):
        from app.tools.site_structure_function_features import build_site_structure_function_features

        pdb_data = """\
ATOM      1  N   ALA B   5A      0.000   1.000   0.000  1.00 20.00           N
ATOM      2  CA  ALA B   5A      0.000   0.000   0.000  1.00 20.00           C
ATOM      3  C   ALA B   5A      1.000   0.000   0.000  1.00 20.00           C
END
"""
        result = await build_site_structure_function_features(
            pdb_data=pdb_data,
            chain_id="B",
            residue_mappings=[
                {
                    "chain_id": "B",
                    "pdb_residue_no": 5,
                    "insertion_code": "A",
                    "uniprot_position": 205,
                    "mapping_confidence": "curated_sifts",
                }
            ],
        )

        assert result["feature_count"] == 1
        row = result["features"][0]
        assert row["pdb_position"] == "B:5A"
        assert row["pdb_author_coordinate"] == {
            "chain_id": "B",
            "residue_no": 5,
            "insertion_code": "A",
        }
        assert row["uniprot_coordinate"]["position"] == 205
        assert row["projection_eligibility"]["uniprot"] is True

    async def test_missing_pdb_returns_error_contract(self):
        from app.tools.site_structure_function_features import build_site_structure_function_features

        result = await build_site_structure_function_features()

        assert result["found"] is False
        assert result["error_code"] == "MISSING_PDB"
        assert result["features"] == []
        assert result["feature_table_contract"]["status"] == "blocked"
        assert "no_structure_features_computed" in result["feature_table_contract"]["blocked_reasons"]

    async def test_site_feature_tool_registered(self):
        from app.tools.registry import ToolRegistry

        ToolRegistry.discover()

        tool = ToolRegistry.get_tool("build_site_structure_function_features")
        assert tool is not None
        assert tool.category == "structure"
