from verify_readiness_snapshot_consistency import verify


def test_current_readiness_snapshot_is_consistent():
    result = verify(__import__('pathlib').Path('.'))
    assert result["ok"] is True
