from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build_release_worktree_manifest.py"
SPEC = importlib.util.spec_from_file_location("release_worktree_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_alignment_summary_is_manual_without_release_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    result = MODULE._alignment_summary()
    assert result["status"] == "manual_required"
    assert result["failures"] == []
    assert "release manifest missing" in result["detail"]


def test_build_manifest_keeps_alignment_and_secret_boundaries(monkeypatch, tmp_path):
    monkeypatch.setattr(MODULE, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(MODULE, "_run_git", lambda args: "abc123" if args == ["rev-parse", "--short", "HEAD"] else "")
    result = MODULE.build_manifest()
    assert result["release_alignment"]["status"] == "manual_required"
    assert result["network_io"] == "not_executed"
    assert result["destructive_actions"] == "not_executed"
    assert result["secrets_printed"] is False
    json.dumps(result)
