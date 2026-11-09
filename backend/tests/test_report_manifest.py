import hashlib
import json

from app.services.report_manifest import (
    build_report_manifest,
    manifest_sha256,
)


def test_manifest_contains_input_hash_schema_sources_and_runtime():
    manifest = build_report_manifest(
        inputs={"protein.pdb": b"ATOM\n"},
        report_schema_version="1.0",
        tools=[{"name": "foldseek", "version": "9.1", "status": "completed"}],
        models=[{"provider": "openai", "model": "gpt-6-sol"}],
        databases=[{"name": "PDB", "version": "2026-01"}],
        runtime={"python": "3.12"},
        generated_at="2026-10-17T00:00:00Z",
        revision="abc123",
    )
    assert manifest["report_schema_version"] == "1.0"
    assert manifest["inputs"][0]["sha256"] == hashlib.sha256(b"ATOM\n").hexdigest()
    assert manifest["tools"][0]["name"] == "foldseek"
    assert manifest["models"][0]["model"] == "gpt-6-sol"
    assert manifest["databases"][0]["name"] == "PDB"
    assert manifest["runtime"]["python"] == "3.12"
    assert manifest["generated_at"] == "2026-10-17T00:00:00Z"
    assert manifest["revision"] == "abc123"


def test_manifest_drops_sensitive_values_and_hash_is_stable():
    kwargs = dict(
        inputs={"x": "payload"},
        report_schema_version="1.0",
        tools=[{"name": "tool", "token": "secret", "Authorization": "Bearer secret"}],
        models=[{"model": "gpt-6-sol", "api_key": "secret"}],
        databases=[{"name": "db", "Cookie": "secret"}],
        runtime={"env": {"TOKEN": "secret", "normal": "ok", "endpoint": "https://example.invalid?token=url-secret"}},
        generated_at="2026-10-17T00:00:00Z",
        revision="abc123",
    )
    first = build_report_manifest(**kwargs)
    second = build_report_manifest(**dict(reversed(list(kwargs.items()))))
    serialized = json.dumps(first, ensure_ascii=False, sort_keys=True)
    assert "secret" not in serialized
    assert "url-secret" not in serialized
    assert "Bearer" not in serialized
    assert first == second
    assert manifest_sha256(first) == manifest_sha256(second)
    assert len(manifest_sha256(first)) == 64
