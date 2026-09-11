def test_fetch_script_imports():
    import fetch_skid_uniprot_sequences as module
    assert callable(module.main)
