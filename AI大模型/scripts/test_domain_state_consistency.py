import json
from pathlib import Path

from domain_state_consistency import build_summary


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(path: Path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_summary_counts_single_and_multi_occurrence_rows(tmp_path):
    evidence = tmp_path / "evidence.json"
    decisions = tmp_path / "decisions.json"
    applied = tmp_path / "applied.json"
    sidecar = tmp_path / "sidecar.json"
    _write_json(evidence, {"input_rows": 4, "rows_with_exact_pfam_interval": 3, "rows_without_exact_pfam_interval": 1})
    _write_json(decisions, {"evidence_rows": 4, "merged_decision_rows": 3, "interpro_program_reviewed_decisions": 2})
    _write_json(applied, {"queue_rows": 4, "output_rows": 3, "usable_for_position_features": 2, "status_counts": {"domain_interval_curated": 2, "domain_interval_unresolved": 1}})
    _write_json(sidecar, {"feature_rows": 1, "valid_rows": 1, "safe_for_position_features_rows": 1})

    summary = build_summary(evidence, decisions, applied, sidecar)

    assert summary["status"] == "blocked"
    assert summary["totals"] == {"evidence": 4, "single_interval_usable": 2, "multi_occurrence_usable": 1, "unresolved": 1}
    assert "single_interval_plus_sidecar" in summary["allowed_feature_scopes"]
    assert summary["consistency"]["ok"] is True


def test_summary_fails_closed_on_mismatched_counts(tmp_path):
    paths = [tmp_path / name for name in ("e.json", "d.json", "a.json", "s.json")]
    _write_json(paths[0], {"input_rows": 4, "rows_with_exact_pfam_interval": 4})
    _write_json(paths[1], {"evidence_rows": 3, "merged_decision_rows": 3, "interpro_program_reviewed_decisions": 3})
    _write_json(paths[2], {"queue_rows": 4, "output_rows": 3, "usable_for_position_features": 3, "status_counts": {"domain_interval_curated": 3}})
    _write_json(paths[3], {"feature_rows": 0, "valid_rows": 0, "safe_for_position_features_rows": 0})

    summary = build_summary(*paths)

    assert summary["status"] == "blocked_inconsistent"
    assert summary["consistency"]["ok"] is False
    assert summary["consistency"]["errors"]
