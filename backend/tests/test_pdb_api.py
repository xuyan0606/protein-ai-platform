"""Black-box tests for PDB analysis and residue mapping endpoints."""

from pathlib import Path

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User


MINI_PDB = """\
HEADER    TEST STRUCTURE
ATOM      1  N   MET A   5      11.104  13.207  12.411  1.00 20.00           N
ATOM      2  CA  MET A   5      12.560  13.241  12.519  1.00 20.00           C
ATOM      3  C   ALA A   6      13.101  14.650  12.778  1.00 20.00           C
ATOM      4  O   ALA A   6      12.452  15.653  12.515  1.00 20.00           O
ATOM      5  N   GLY B  10      15.104  10.207  11.411  1.00 20.00           N
ATOM      6  CA  GLY B  10      16.560  10.241  11.519  1.00 20.00           C
END
"""


async def _create_user(session, email: str = "pdb@example.com") -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="PDB User",
    )
    session.add(user)
    await session.flush()
    await session.commit()
    return user


class TestPDBResidueMappingAPI:
    def test_parser_reads_real_mmcif(self):
        from app.services.pdb_parser import parse_pdb

        cif = Path(__file__).resolve().parents[2] / "deploy_data/pdb/4HHB.cif"
        analysis = parse_pdb(cif.read_text(encoding="utf-8"))

        assert analysis["total_atoms"] == 4558
        assert analysis["total_residues"] == 574
        assert len(analysis["chains"]) == 4
        assert analysis["resolution"] == 1.74
        assert analysis["method"] == "X-RAY DIFFRACTION"

    async def test_parse_rejects_header_without_protein_atoms(self, client, session):
        user = await _create_user(session, email="pdb-empty-coordinates@example.com")
        client.cookies.set("pa_token", create_access_token(user.id))

        response = await client.post("/api/pdb/parse", json={"pdb_data": "HEADER    FAKE STRUCTURE\nEND\n"})

        assert response.status_code == 400
        assert "No protein coordinates" in response.json()["detail"]

    async def test_parse_accepts_seqres_first_pdb(self, client, session):
        user = await _create_user(session, email="pdb-seqres-first@example.com")
        client.cookies.set("pa_token", create_access_token(user.id))

        response = await client.post("/api/pdb/parse", json={"pdb_data": "SEQRES   1 A    2  MET ALA\n" + MINI_PDB})

        assert response.status_code == 200
        assert response.json()["total_residues"] == 3

    def test_parser_reads_swiss_model_expdta(self):
        from app.services.pdb_parser import parse_pdb

        analysis = parse_pdb(
            "TITLE     SWISS-MODEL SERVER\n"
            "EXPDTA    THEORETICAL MODEL (SWISS-MODEL SERVER)\n"
            + MINI_PDB
        )

        assert analysis["method"] == "THEORETICAL MODEL (SWISS-MODEL SERVER)"

    def test_parser_preserves_subunit_b_factor_as_raw_protein_field(self):
        from app.services.pdb_parser import parse_pdb

        atom = MINI_PDB.splitlines()[1]
        normalized_atom = atom[:60] + f"{0.92:6.2f}" + atom[66:]
        analysis = parse_pdb("\n".join([MINI_PDB.splitlines()[0], normalized_atom, "END"]))

        assert analysis["b_factor_stats"]["mean"] == 0.92
        assert analysis["b_factor_stats"]["atom_count"] == 1
        assert "raw PDB temperature-factor column" in analysis["b_factor_scope"]
        assert "interpretation depends on structure source" in analysis["b_factor_scope"]

    async def test_mapping_from_raw_pdb(self, client, session):
        user = await _create_user(session)
        client.cookies.set("pa_token", create_access_token(user.id))

        response = await client.post(
            "/api/pdb/mapping",
            json={
                "pdb_data": MINI_PDB,
                "chain_id": "A",
                "uniprot_id": "PTEST1",
                "uniprot_start": 101,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["found"] is True
        assert body["mapping_count"] == 2
        assert body["mappings"][0]["pdb_residue_no"] == 5
        assert body["mappings"][0]["uniprot_position"] is None
        assert body["mappings"][0]["coordinate_sequence_position"] == 1
        assert body["coordinate_systems"] == ["coordinate_sequence", "pdb_author"]

    async def test_mapping_from_raw_pdb_can_use_local_sifts_file(self, client, session, monkeypatch, tmp_path):
        user = await _create_user(session, email="pdb-sifts@example.com")
        client.cookies.set("pa_token", create_access_token(user.id))

        mapping_dir = tmp_path / "sifts"
        mapping_dir.mkdir()
        (mapping_dir / "1abc.csv").write_text(
            "pdb_id,chain_id,pdb_residue_no,residue_aa,uniprot_id,uniprot_position\n"
            "1abc,A,5,M,PTEST1,205\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(settings, "SIFTS_MAPPING_PATH", str(mapping_dir), raising=False)

        response = await client.post(
            "/api/pdb/mapping",
            json={
                "pdb_data": MINI_PDB,
                "pdb_id": "1abc",
                "chain_id": "A",
                "uniprot_id": "PTEST1",
                "uniprot_start": 101,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "local_sifts_mapping"
        assert body["mapping_count"] == 1
        assert body["mappings"][0]["uniprot_position"] == 205

    async def test_mapping_by_name_enforces_user_prefix(self, client, session):
        user = await _create_user(session, email="pdb-access@example.com")
        client.cookies.set("pa_token", create_access_token(user.id))

        response = await client.post(
            "/api/pdb/mapping-by-name",
            json={"object_name": "uploads/user_999/pdb/test.pdb"},
        )

        assert response.status_code == 403


class TestPDBStructureSearchAPI:
    async def test_structure_search_from_raw_pdb(self, client, session, monkeypatch):
        user = await _create_user(session, email="pdb-search@example.com")
        client.cookies.set("pa_token", create_access_token(user.id))
        monkeypatch.setattr(settings, "FOLDSEEK_API_URL", "", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_BINARY", "", raising=False)
        monkeypatch.setattr(settings, "FOLDSEEK_DATABASE_PDB", "", raising=False)

        response = await client.post(
            "/api/pdb/structure-search",
            json={
                "pdb_data": MINI_PDB,
                "database": "pdb",
                "max_results": 5,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert body["error_code"] == "FOLDSEEK_NOT_CONFIGURED"
        assert body["backend"] == "summary_only"
        assert body["query_structure"]["chain_count"] == 2

    async def test_structure_search_by_name_enforces_user_prefix(self, client, session):
        user = await _create_user(session, email="pdb-search-access@example.com")
        client.cookies.set("pa_token", create_access_token(user.id))

        response = await client.post(
            "/api/pdb/structure-search-by-name",
            json={"object_name": "uploads/user_999/pdb/test.pdb"},
        )

        assert response.status_code == 403
