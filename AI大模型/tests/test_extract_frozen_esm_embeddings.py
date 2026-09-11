def test_embedding_script_imports():
    import extract_frozen_esm_embeddings as module
    assert callable(module.main)
