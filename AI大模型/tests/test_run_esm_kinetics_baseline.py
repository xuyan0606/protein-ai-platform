def test_esm_baseline_imports():
    import run_esm_kinetics_baseline as module
    assert callable(module.main)
