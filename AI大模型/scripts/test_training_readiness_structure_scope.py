import json


def test_structure_cache_is_marked_sample_only_when_sample_is_partial():
    report = json.load(open("reports/training_readiness_report.json"))
    assert report["structure_cache"]["coordinate_features_scope"] == "sample_only"
    assert report["structure_cache"]["full_cache_ready"] is False
