import json


def test_master_board_distinguishes_partial_structure_and_msa_runtime_ready():
    report = json.load(open("reports/master_readiness_board.json"))
    streams = {s["stream"]: s for s in report["streams"]}
    assert streams["structure_cache"]["status"] == "partial_ready"
    assert streams["structure_cache"]["ready"] is False
    assert streams["msa_conservation"]["status"] == "ready"
    assert streams["msa_conservation"]["ready"] is True
