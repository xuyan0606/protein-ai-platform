def test_queue_script_imports():
    import build_skid_sequence_resolution_queue as module
    assert callable(module.main)
