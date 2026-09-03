import json


def test_master_board_separates_strict_and_partial_ready_counts():
    report = json.load(open("reports/master_readiness_board.json"))
    assert report["ready_streams"] == 1
    assert report["partial_ready_streams"] >= 3
