import json


def test_master_board_uses_partial_ready_domain_state():
    report = json.load(open("reports/master_readiness_board.json"))
    stream = next(item for item in report["streams"] if item["stream"] == "domain_intervals")
    assert stream["status"] == "partial_ready"
    assert stream["current"]["consistency_snapshot"]["totals"]["unresolved"] == 2
