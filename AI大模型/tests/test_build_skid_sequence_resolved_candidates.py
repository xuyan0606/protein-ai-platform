def test_candidate_script_imports():
    import build_skid_sequence_resolved_candidates as module
    assert callable(module.main)
