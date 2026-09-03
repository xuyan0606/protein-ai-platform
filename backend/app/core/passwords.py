"""Shared password hashing helpers with bcrypt/passlib compatibility shims."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def _ensure_bcrypt_metadata(module: Any | None = None) -> Any | None:
    """Backfill bcrypt.__about__.__version__ for passlib on bcrypt 4.x.

    Passlib 1.7.x still probes ``bcrypt.__about__.__version__`` during backend
    initialization. Newer bcrypt releases removed ``__about__`` and expose only
    ``__version__``, which triggers noisy warnings even though hashing still
    works. Restoring that tiny compatibility surface keeps existing bcrypt
    hashes valid without pinning an older bcrypt runtime.
    """
    bcrypt_module = module
    if bcrypt_module is None:
        try:
            import bcrypt as bcrypt_module
        except ImportError:
            return None

    about = getattr(bcrypt_module, "__about__", None)
    if about is not None:
        return bcrypt_module

    version = getattr(bcrypt_module, "__version__", None)
    if not version:
        return bcrypt_module

    bcrypt_module.__about__ = SimpleNamespace(__version__=version)
    return bcrypt_module


_ensure_bcrypt_metadata()

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
