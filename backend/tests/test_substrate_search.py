import asyncio

from app.tools import substrate_search as adapter


def test_substrate_search_validates_namespace_and_query():
    try:
        asyncio.run(adapter.substrate_search("", "name"))
    except ValueError as exc:
        assert "MISSING_SUBSTRATE_QUERY" in str(exc)
    else:
        raise AssertionError("empty query must fail closed")


def test_substrate_search_returns_auditable_pubchem_record(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"PropertyTable": {"Properties": [{"CID": 1, "Title": "ethanol", "CanonicalSMILES": "CCO", "InChIKey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"}]}}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            assert "/name/ethanol/" in url
            return Response()

    monkeypatch.setattr(adapter.httpx, "AsyncClient", lambda timeout: Client())
    result = asyncio.run(adapter.substrate_search("ethanol"))
    assert result["status"] == "completed_substrate_lookup"
    assert result["results"][0]["canonical_smiles"] == "CCO"
    assert result["evidence_level"] == "database_record"
