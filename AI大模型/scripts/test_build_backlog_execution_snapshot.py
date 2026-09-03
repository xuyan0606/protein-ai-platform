import json
from build_backlog_execution_snapshot import build_snapshot


def test_snapshot_preserves_fail_closed_gates(tmp_path):
    base = tmp_path; (base / "reports").mkdir()
    report = json.load(open("reports/training_readiness_report.json"))
    (base / "reports/training_readiness_report.json").write_text(json.dumps(report))
    master = json.load(open("reports/master_readiness_board.json"))
    (base / "reports/master_readiness_board.json").write_text(json.dumps(master))
    out = build_snapshot(base)
    assert out["gates"]["strict_ready_streams"] == 1
    assert out["gates"]["training_execution_allowed"] is False
