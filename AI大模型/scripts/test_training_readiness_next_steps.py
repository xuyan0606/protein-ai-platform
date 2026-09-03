import json


def test_readiness_next_steps_do_not_claim_full_domain_repair_needed():
    report = json.load(open("reports/training_readiness_report.json"))
    domain_steps = [step for step in report["next_steps"] if "domain" in step]
    assert domain_steps == ["review 2 unresolved domain intervals via domain_unresolved_review_packet_20260829.json"]
