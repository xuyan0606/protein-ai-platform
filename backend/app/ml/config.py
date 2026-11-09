"""ML model configuration."""

from pydantic_settings import BaseSettings


class MLSettings(BaseSettings):
    """ML inference settings — loaded from env vars with ML_ prefix."""

    # Model selection
    ESM2_MODEL: str = "esm2_t33_650M_UR50D"
    ESM2_EMBEDDING_LAYER: int = 33

    # Cache
    MODEL_CACHE_DIR: str = "./.model_cache"
    PRELOAD_MODELS: bool = False

    # CPU inference
    NUM_THREADS: int = 4

    # Memory safety
    MAX_MODEL_MEMORY_GB: float = 8.0

    model_config = {"env_prefix": "ML_", "env_file": ".env", "extra": "ignore"}


ml_settings = MLSettings()
