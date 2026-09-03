from validate_workstream_acceptance_decisions import stream_decision_sets


def test_needs_more_info_is_decided_but_not_accepted():
    decided, accepted = stream_decision_sets([
        {"stream": "active_learning", "valid": True, "accepted": False},
    ])
    assert decided == ["active_learning"]
    assert accepted == []


def test_accepted_stream_is_both_decided_and_accepted():
    decided, accepted = stream_decision_sets([
        {"stream": "msa_conservation", "valid": True, "accepted": True},
    ])
    assert decided == ["msa_conservation"]
    assert accepted == ["msa_conservation"]


def test_invalid_stream_record_is_not_decided():
    decided, accepted = stream_decision_sets([
        {"stream": "plate_feedback", "valid": False, "accepted": False},
    ])
    assert decided == []
    assert accepted == []
