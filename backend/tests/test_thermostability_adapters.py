"""Model-service contracts only; no database or real network calls."""

import copy
import hashlib
import json

import httpx
import pytest

from app.tools import thermostability_adapters as adapters


SEQUENCE = "ACDE"


def digest(value):
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(value.encode()).hexdigest()


def pdb(sequence=SEQUENCE, confidence=(80., 81., 82., 83.)):
    names = {"A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU"}
    return "\n".join(
        f"ATOM  {i:5d}  CA  {names[aa]} A{i:4d}    {float(i):8.3f}{0.:8.3f}{0.:8.3f}  1.00{confidence[i-1]:6.2f}           C"
        for i, aa in enumerate(sequence, 1)
    )


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for prefix in ("DDGUN", "COLABFOLD", "EVCOUPLINGS"):
        for suffix in ("SERVICE_URL", "SERVICE_TOKEN", "LOCAL_MSA_PATH", "ALLOW_PUBLIC_MSA", "SERVICE_TIMEOUT_SECONDS", "MSA_SOURCE"):
            monkeypatch.delenv(f"{prefix}_{suffix}", raising=False)


def service(monkeypatch, model, update=None):
    calls = []

    async def request(prefix, endpoint, payload, timeout):
        calls.append((prefix, endpoint, payload, timeout))
        raw = {"source": "real-model-output", "scores": [1.2]}
        result = {
            "status": "completed", "model": model, "algorithm_commit": "abcdef1234567",
            "database_version": "fixture-db-20261103", "model_version": "fixture-1",
            "sequence_sha256": digest(payload["sequence"]), "input_sha256": digest(payload),
            "evidence": {"raw_result": raw, "raw_result_sha256": digest(raw)},
        }
        if model == "DDGun":
            result.update(mode=payload["mode"], units="kcal/mol",
                          sign_convention="positive=increased unfolding stability",
                          predictions=[{"mutation": m, "ddg_kcal_mol": 1.2} for m in payload["mutations"]],
                          wild_type={"mutation": "WT", "ddg_kcal_mol": 0.0})
        elif model == "ColabFold":
            result.update(pdb_data=pdb(), chain_id="A", plddt=[80., 81., 82., 83.],
                          msa_policy=payload["msa_policy"])
        else:
            result.update(couplings=[{"position_i": 1, "position_j": 3, "score": 0.8}])
        if update:
            update(result)
        return result, digest(json.dumps(result, default=str))

    monkeypatch.setenv(f"{model.upper()}_SERVICE_URL", "http://model.internal")
    monkeypatch.setattr(adapters, "_request", request)
    return calls


@pytest.mark.asyncio
async def test_unconfigured_is_blocked_with_input_provenance():
    result = await adapters.ddgun_predict(SEQUENCE, ["A1V"])
    assert result["status"] == "blocked"
    assert "DDGUN_SERVICE_URL" in result["blocked_reason"]
    assert result["sequence_sha256"] == digest(SEQUENCE)
    assert result["predictions"] == []


@pytest.mark.asyncio
async def test_ddgun_complete_raw_units_and_evidence(monkeypatch):
    calls = service(monkeypatch, "DDGun")
    result = await adapters.ddgun_predict("ac de", ["a1v", "C2A"])
    assert result["status"] == "completed"
    assert result["predictions"][0]["ddg_kcal_mol"] == 1.2
    assert result["units"] == "kcal/mol"
    assert result["candidate_coverage"] == {"requested": 2, "returned": 2, "complete": True}
    assert result["evidence"]["raw_result_sha256"]
    assert result["evidence"]["raw_http_response_sha256"]
    assert calls[0][2]["mode"] == "sequence"
    assert "tm" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("mutations", [["C1V"], ["A0V"], ["A1A"], ["A1V", "A1V"], [], ["A1V:K2A"]])
async def test_invalid_candidates_never_call_service(monkeypatch, mutations):
    calls = service(monkeypatch, "DDGun")
    result = await adapters.ddgun_predict(SEQUENCE, mutations)
    assert result["status"] == "blocked"
    assert not calls


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    lambda r: r.update(model="ThermoMPNN"),
    lambda r: r.update(sequence_sha256="0" * 64),
    lambda r: r.update(input_sha256="0" * 64),
    lambda r: r.update(algorithm_commit="unknown"),
    lambda r: r.update(database_version="unknown"),
    lambda r: r.update(status="queued"),
    lambda r: r.update(predictions=[]),
    lambda r: r["predictions"].append(copy.deepcopy(r["predictions"][0])),
    lambda r: r["predictions"][0].update(ddg_kcal_mol=float("nan")),
    lambda r: r["predictions"][0].update(ddg_kcal_mol=True),
    lambda r: r["wild_type"].update(ddg_kcal_mol=1.0),
    lambda r: r.update(sign_convention="positive=destabilizing"),
    lambda r: r["evidence"].update(raw_result_sha256="0" * 64),
])
async def test_ddgun_rejects_untrusted_results(monkeypatch, change):
    service(monkeypatch, "DDGun", change)
    result = await adapters.ddgun_predict(SEQUENCE, ["A1V"])
    assert result["status"] == "blocked"
    assert result["predictions"] == []
    assert result["blocked_reason"]
    assert result["rejected_response_sha256"]


@pytest.mark.asyncio
async def test_structure_ddgun_binds_chain_sequence(monkeypatch):
    calls = service(monkeypatch, "DDGun")
    assert (await adapters.ddgun_predict(SEQUENCE, ["A1V"], pdb()))["status"] == "completed"
    assert calls[0][2]["mode"] == "3d"
    assert (await adapters.ddgun_predict(SEQUENCE, ["A1V"], pdb("AAAA")))["status"] == "blocked"
    assert len(calls) == 1
    shifted = pdb().replace(" A   1", " A 101")
    result = await adapters.ddgun_predict(SEQUENCE, ["A1V"], shifted)
    assert result["status"] == "blocked"
    assert "numbering_mapping_required" in result["blocked_reason"]


@pytest.mark.asyncio
async def test_colabfold_never_silently_uses_public_msa(monkeypatch, tmp_path):
    calls = service(monkeypatch, "ColabFold")
    assert (await adapters.colabfold_predict(SEQUENCE))["status"] == "blocked"
    assert (await adapters.colabfold_predict(SEQUENCE, "public"))["status"] == "blocked"
    assert not calls
    path = tmp_path / "query.a3m"
    path.write_text(">query\nACDE\n>homolog\nAC-E\n")
    monkeypatch.setenv("COLABFOLD_LOCAL_MSA_PATH", str(path))
    result = await adapters.colabfold_predict(SEQUENCE)
    assert result["status"] == "completed"
    assert result["mean_plddt"] == 81.5
    assert calls[0][2]["allow_public_msa"] is False
    monkeypatch.setenv("COLABFOLD_ALLOW_PUBLIC_MSA", "true")
    assert (await adapters.colabfold_predict(SEQUENCE, "public"))["status"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    lambda r: r.update(pdb_data=pdb("AAAA")),
    lambda r: r.update(plddt=[80.]),
    lambda r: r.update(plddt=[80., 80., 80., float("inf")]),
    lambda r: r.update(msa_policy="local"),
])
async def test_colabfold_rejects_wrong_structure_or_policy(monkeypatch, change):
    service(monkeypatch, "ColabFold", change)
    monkeypatch.setenv("COLABFOLD_ALLOW_PUBLIC_MSA", "true")
    assert (await adapters.colabfold_predict(SEQUENCE, "public"))["status"] == "blocked"


@pytest.mark.asyncio
async def test_colabfold_rejects_plddt_hidden_by_high_pdb_bfactor(monkeypatch):
    service(monkeypatch, "ColabFold", lambda r: r.update(plddt=[20.] * len(SEQUENCE)))
    monkeypatch.setenv("COLABFOLD_ALLOW_PUBLIC_MSA", "true")
    result = await adapters.colabfold_predict(SEQUENCE, "public")
    assert result["status"] == "blocked"
    assert "pLDDT disagrees" in result["blocked_reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize("offset,expected", [(0.019, "completed"), (0.02, "completed"), (0.021, "blocked")])
async def test_colabfold_plddt_matches_pdb_ca_with_rounding_tolerance(monkeypatch, offset, expected):
    service(monkeypatch, "ColabFold", lambda r: r.update(plddt=[value + offset for value in r["plddt"]]))
    monkeypatch.setenv("COLABFOLD_ALLOW_PUBLIC_MSA", "true")
    assert (await adapters.colabfold_predict(SEQUENCE, "public"))["status"] == expected


@pytest.mark.asyncio
async def test_evcouplings_insufficient_msa_skips_without_service(monkeypatch):
    calls = service(monkeypatch, "EVcouplings")
    result = await adapters.evcouplings_analyze(SEQUENCE, {"neff": 2, "coverage": .4, "sequence_count": 2})
    assert result["status"] == "skipped"
    assert result["couplings"] == []
    assert not calls


@pytest.mark.asyncio
async def test_evcouplings_quality_gate_and_bound_couplings(monkeypatch):
    calls = service(monkeypatch, "EVcouplings")
    quality = {"neff": 60, "coverage": .9, "sequence_count": 100}
    result = await adapters.evcouplings_analyze(SEQUENCE, quality, ">query\nACDE\n>h\nAC-E\n")
    assert result["status"] == "completed"
    assert calls[0][1] == "/couplings"
    service(monkeypatch, "EVcouplings", lambda r: r["couplings"][0].update(position_j=100))
    result = await adapters.evcouplings_analyze(SEQUENCE, quality, ">query\nACDE\n>h\nAC-E\n")
    assert result["status"] == "blocked"


@pytest.mark.asyncio
async def test_http_failure_is_blocked_without_leaking_credentials(monkeypatch):
    service(monkeypatch, "DDGun")

    async def fail(*args):
        raise httpx.ReadTimeout("private-service-secret")

    monkeypatch.setattr(adapters, "_request", fail)
    result = await adapters.ddgun_predict(SEQUENCE, ["A1V"])
    assert result["status"] == "blocked"
    assert "private-service-secret" not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("sequence", ["", "AXDE", "A" * 4001, None])
async def test_invalid_or_unbounded_sequence_blocks(monkeypatch, sequence):
    calls = service(monkeypatch, "DDGun")
    assert (await adapters.ddgun_predict(sequence, ["A1V"]))["status"] == "blocked"
    assert not calls


@pytest.mark.asyncio
async def test_unused_structure_fields_are_still_bounded(monkeypatch):
    calls = service(monkeypatch, "DDGun")
    assert (await adapters.ddgun_predict(SEQUENCE, ["A1V"], chain_id="A" * 100))["status"] == "blocked"
    monkeypatch.setattr(adapters, "_MAX_TEXT", 10)
    assert (await adapters.ddgun_predict(SEQUENCE, ["A1V"], pdb_data=" " * 11))["status"] == "blocked"
    assert not calls


@pytest.mark.asyncio
async def test_missing_quality_skips_and_unconfigured_quality_ready_blocks():
    assert (await adapters.evcouplings_analyze(SEQUENCE, None))["status"] == "skipped"
    result = await adapters.evcouplings_analyze(
        SEQUENCE, {"neff": 60, "coverage": .9, "sequence_count": 100}, ">q\nACDE\n")
    assert result["status"] == "blocked"
    assert "EVCOUPLINGS_SERVICE_URL" in result["blocked_reason"]


@pytest.mark.asyncio
async def test_transport_posts_exact_request_and_hashes_raw_response(monkeypatch):
    original_client = httpx.AsyncClient
    seen = []
    raw = b'{"status":"completed", "x":1}'

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=raw)

    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        assert kwargs["timeout"].read == 180.
        return original_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(adapters.httpx, "AsyncClient", client)
    monkeypatch.setenv("DDGUN_SERVICE_URL", "http://model.internal")
    monkeypatch.setenv("DDGUN_SERVICE_TOKEN", "secret-token")
    response, raw_hash = await adapters._request("DDGUN", "/predict", {"sequence": SEQUENCE}, 180.)
    assert response == {"status": "completed", "x": 1}
    assert raw_hash == hashlib.sha256(raw).hexdigest()
    assert seen[0].url.path == "/predict"
    assert json.loads(seen[0].content) == {"sequence": SEQUENCE}
    assert seen[0].headers["Authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_cpu_service_timeout_is_configurable_and_bounded(monkeypatch):
    original_client = httpx.AsyncClient
    seen = []

    def client(**kwargs):
        seen.append(kwargs["timeout"].read)
        return original_client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"status": "completed"})), **kwargs)

    monkeypatch.setattr(adapters.httpx, "AsyncClient", client)
    monkeypatch.setenv("DDGUN_SERVICE_URL", "http://model.internal")
    monkeypatch.setenv("DDGUN_SERVICE_TIMEOUT_SECONDS", "3600")
    await adapters._request("DDGUN", "/predict", {"sequence": SEQUENCE}, 180.)
    assert seen == [3600.]
    for invalid in ("nan", "inf", "0", "14401", "abc"):
        monkeypatch.setenv("DDGUN_SERVICE_TIMEOUT_SECONDS", invalid)
        with pytest.raises(ValueError, match="SERVICE_TIMEOUT_SECONDS"):
            await adapters._request("DDGUN", "/predict", {"sequence": SEQUENCE}, 180.)
    assert seen == [3600.]


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["ftp://model", "http://secret@model", "https://model?token=x"])
async def test_unsafe_service_url_blocks_without_network(monkeypatch, url):
    monkeypatch.setenv("DDGUN_SERVICE_URL", url)
    result = await adapters.ddgun_predict(SEQUENCE, ["A1V"])
    assert result["status"] == "blocked"


@pytest.mark.asyncio
async def test_transport_response_limit(monkeypatch):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(adapters, "_MAX_RESPONSE", 4)
    monkeypatch.setenv("DDGUN_SERVICE_URL", "http://model.internal")
    monkeypatch.setattr(adapters.httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b'{"oversized": true}')), **kwargs))
    result = await adapters.ddgun_predict(SEQUENCE, ["A1V"])
    assert result["status"] == "blocked"
    assert "16 MB" in result["blocked_reason"]

@pytest.mark.asyncio
async def test_colabfold_operator_can_select_per_input_private_local_search(monkeypatch):
    monkeypatch.setenv('COLABFOLD_MSA_SOURCE', 'service_local_search')
    def update(result):
        result.update(msa_source='service_local_search', msa_depth=2, msa_sha256='b'*64,
                      msa_database='uniprot20_2016_02')
    calls = service(monkeypatch, 'ColabFold', update)
    result = await adapters.colabfold_predict(SEQUENCE, 'local')
    assert result['status'] == 'completed'
    assert result['msa_source'] == 'service_local_search' and result['msa_depth'] == 2
    assert calls[0][2]['alignment'] == ''
    assert calls[0][2]['allow_public_msa'] is False
    assert calls[0][2]['msa_source'] == 'service_local_search'


@pytest.mark.asyncio
async def test_colabfold_local_search_requires_retained_msa_provenance(monkeypatch):
    monkeypatch.setenv('COLABFOLD_MSA_SOURCE', 'service_local_search')
    service(monkeypatch, 'ColabFold')
    result = await adapters.colabfold_predict(SEQUENCE, 'local')
    assert result['status'] == 'blocked' and 'MSA' in result['blocked_reason']
