import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_builder():
    path = PROJECT_ROOT / "scripts" / "build_tool_orchestration_matrix.py"
    spec = importlib.util.spec_from_file_location("tool_orchestration_matrix", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registered_tools_have_explicit_capability_contracts():
    report = _load_builder().build_report()
    assert report["registered_tool_count"] == 62
    assert report["capability_audited_count"] == 62
    assert report["unknown_capability_tools"] == []
    assert report["async_tool_count"] == 13
    assert all(row["minimum_artifacts"] for row in report["rows"])
    required_keys = {"requires", "provides", "evidence_level", "runtime_mode", "license_status"}
    assert all(required_keys <= set(row) for row in report["rows"])
    assert all(row["runtime_mode"] in {"inline_sync", "async_worker"} for row in report["rows"])
    assert all(row["evidence_level"] in {"runtime_or_source_evidence", "proxy_or_ranking_only", "unverified"} for row in report["rows"])


def test_generated_contract_matches_typed_dependency_constants():
    module = _load_builder()
    report = module.build_report()
    by_name = {row["tool"]: row for row in report["rows"]}
    from app.services.tool_orchestration_contract import TOOL_PROVIDES, TOOL_REQUIRES

    for name, row in by_name.items():
        assert row["requires"] == sorted(TOOL_REQUIRES.get(name, frozenset()))
        assert row["provides"] == sorted(TOOL_PROVIDES.get(name, frozenset()))
