"""Black-box tests for PDB analysis and residue mapping endpoints."""

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
        assert body["mappings"][0]["uniprot_position"] == 101

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
