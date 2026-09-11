def test_audit_script_imports():
    import audit_skid_kinetics_source as module
    assert callable(module.main)
