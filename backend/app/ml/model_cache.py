"""Thread-safe shared model cache.

Prevents duplicate model loads when multiple ThreadPoolExecutor workers
concurrently call the same tool.
"""

import threading
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ModelCache:
    """Singleton cache for loaded ML models.

    Usage:
        cache = ModelCache.instance()
        model = cache.get("esm2", lambda: load_esm2_model())
    """

    _instance: "ModelCache | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._models: dict[str, Any] = {}
        self._load_locks: dict[str, threading.Lock] = {}

    @classmethod
    def instance(cls) -> "ModelCache":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get(self, name: str, loader: Callable[[], Any]) -> Any:
        """Get a cached model, loading it if not present.

        Thread-safe: ensures only one thread loads while others wait.
        """
        if name in self._models:
            return self._models[name]

        # Per-model lock to allow concurrent loads of different models
        if name not in self._load_locks:
            with self._lock:
                if name not in self._load_locks:
                    self._load_locks[name] = threading.Lock()

        with self._load_locks[name]:
            # Double-check after acquiring lock
            if name in self._models:
                return self._models[name]

            logger.info("Loading model '%s' (first call — downloading if needed)...", name)
            try:
                model = loader()
                self._models[name] = model
                logger.info("Model '%s' loaded successfully", name)
                return model
            except Exception:
                logger.exception("Failed to load model '%s'", name)
                raise

    def is_loaded(self, name: str) -> bool:
        return name in self._models

    def clear(self) -> None:
        """Clear all cached models (for testing)."""
        with self._lock:
            self._models.clear()
            self._load_locks.clear()
