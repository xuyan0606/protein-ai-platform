import json

from training_readiness_report import domain_architecture_state


def test_domain_state_uses_consistency_snapshot(tmp_path):
    report = tmp_path / "domain.json"
    report.write_text(json.dumps({"totals": {"evidence": 10, "single_interval_usable": 8, "multi_occurrence_usable": 1, "unresolved": 1}, "consistency": {"ok": True}}))
    assert domain_architecture_state(report) == {"rows": 10, "invalid_interval_rows": 1, "usable_for_position_features": True}
