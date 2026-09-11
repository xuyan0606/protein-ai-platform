def test_review_audit_imports():
    import audit_skid_review_candidates as module
    assert callable(module.main)
