import json


def test_readiness_reports_current_feature_stream_states():
    report = json.load(open("reports/training_readiness_report.json"))
    streams = report["feature_streams"]
    assert streams["msa_conservation"] == {
        "targets": 158,
        "present": 158,
        "missing": 0,
        "ready": True,
        "source": "trusted_cache_validated",
    }
    assert streams["structure_chain_mapping"]["remaining_unreviewed_rows"] == 475
    assert streams["experiment_feedback"]["ready_for_training"] is False
