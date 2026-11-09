from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run_release_acceptance.py"
SPEC = importlib.util.spec_from_file_location("release_acceptance", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_report_alignment_is_manual_without_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("RELEASE_MANIFEST", raising=False)
    result = MODULE._report_alignment_result(plan_only=False)
    assert result.status == "manual_required"
    assert "manifest missing" in result.detail
    assert result.data["verified"] is False


def test_report_alignment_is_planned_without_executing_in_plan_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("RELEASE_MANIFEST", raising=False)
    result = MODULE._report_alignment_result(plan_only=True)
    assert result.status == "planned"
    assert result.command[-1] == "--json"


def test_relative_release_manifest_is_resolved_from_project_root(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("RELEASE_MANIFEST", "releases/RELEASE-MANIFEST.json")
    result = MODULE._report_alignment_result(plan_only=False)
    assert result.data["manifest"] == str(tmp_path / "releases/RELEASE-MANIFEST.json")
