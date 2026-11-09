import pytest

from app.services import storage


class RuntimeFailingClient:
    def bucket_exists(self, bucket: str) -> bool:
        raise RuntimeError("UserDisable")

    def put_object(self, *args, **kwargs):
        raise RuntimeError("UserDisable")


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def close(self):
        return None

    def release_conn(self):
        return None


class MissingThenAvailableClient:
    def __init__(self):
        self.calls = 0

    def get_object(self, bucket: str, object_name: str):
        self.calls += 1
        if self.calls == 1:
            error = RuntimeError("NoSuchKey")
            error.code = "NoSuchKey"
            raise error
        return FakeResponse(b"from-object-storage")


@pytest.mark.asyncio
async def test_upload_falls_back_to_local_when_object_storage_is_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(storage.settings, "STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setattr(storage, "_client", None)
    monkeypatch.setattr(storage, "_fallback", False)
    monkeypatch.setattr(storage, "_local_root", None)
    monkeypatch.setattr(storage, "_get_minio_client", lambda: RuntimeFailingClient())

    stored = await storage.upload_file(
        b"hello",
        "sample.txt",
        content_type="text/plain",
        folder="uploads/user_7",
    )

    assert stored["storage"] == "local"
    assert stored["object_name"].startswith("uploads/user_7/")
    assert await storage.download_file(stored["object_name"]) == b"hello"
    assert await storage.delete_file(stored["object_name"]) is True
    assert await storage.delete_file(stored["object_name"]) is False


@pytest.mark.asyncio
async def test_missing_object_does_not_disable_future_object_storage_reads(monkeypatch, tmp_path):
    client = MissingThenAvailableClient()
    monkeypatch.setattr(storage.settings, "STORAGE_LOCAL_PATH", str(tmp_path))
    monkeypatch.setattr(storage, "_client", client)
    monkeypatch.setattr(storage, "_fallback", False)
    monkeypatch.setattr(storage, "_local_root", None)

    with pytest.raises(RuntimeError, match="File not found"):
        await storage.download_file("uploads/missing.pdb")

    assert storage._fallback is False
    assert await storage.download_file("uploads/recovered.pdb") == b"from-object-storage"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_deleting_old_local_upload_after_object_store_recovers_removes_local_copy(monkeypatch, tmp_path):
    class RecoveredClient:
        def remove_object(self, bucket, name):
            pass  # S3 DELETE succeeds for absent keys too.
    monkeypatch.setattr(storage, '_local_root', tmp_path)
    monkeypatch.setattr(storage, '_client', RecoveredClient())
    path = tmp_path / 'uploads/legacy.txt'
    path.parent.mkdir()
    path.write_bytes(b'legacy-local-upload')
    assert await storage.delete_file('uploads/legacy.txt') is True
    assert not path.exists()


def test_object_store_health_recovers_after_transient_failure(monkeypatch):
    monkeypatch.setattr(storage, '_fallback', True)
    def recovered():
        storage._fallback = False
        return object()
    monkeypatch.setattr(storage, '_get_minio_client', recovered)
    assert storage.is_minio_available() is True
