from types import SimpleNamespace

from app.core.passwords import _ensure_bcrypt_metadata, hash_password, verify_password


def test_ensure_bcrypt_metadata_backfills_about_namespace():
    fake_bcrypt = SimpleNamespace(__version__="4.3.0")

    patched = _ensure_bcrypt_metadata(fake_bcrypt)

    assert patched is fake_bcrypt
    assert patched.__about__.__version__ == "4.3.0"


def test_hash_and_verify_password_round_trip():
    hashed = hash_password("password123")

    assert hashed != "password123"
    assert verify_password("password123", hashed) is True
    assert verify_password("wrong-password", hashed) is False
