def test_merge_script_imports():
    import merge_kinetics_review_pass as module
    assert callable(module.main)
