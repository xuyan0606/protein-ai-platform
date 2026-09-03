import json


def test_blockers_include_current_quantified_stream_gaps():
    report = json.load(open("reports/training_readiness_report.json"))
    blockers = report["blockers"]
    assert not any("MSA conservation cache missing" in item for item in blockers)
    assert any("475 human-reviewed rows" in item for item in blockers)
    assert any("7 reviewed rows" in item for item in blockers)
