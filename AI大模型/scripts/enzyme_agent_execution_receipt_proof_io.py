"""Atomic IO helpers shared by enzyme-agent execution receipt proofs."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def acquire_lock(path: Path, timeout_seconds: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None
            time.sleep(0.05)


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_bytes_atomic(path: Path, payload: bytes, *, prefix: str = "receipt-proof", fail_before_replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.{prefix}-", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode)
        if fail_before_replace:
            raise RuntimeError("simulated_receipt_proof_failure_before_replace")
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_json_atomic(path: Path, payload: dict[str, Any], *, prefix: str = "receipt-proof", fail_before_replace: bool = False) -> None:
    write_bytes_atomic(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), prefix=prefix, fail_before_replace=fail_before_replace)


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]], *, prefix: str = "receipt-proof") -> None:
    write_bytes_atomic(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows).encode("utf-8"), prefix=prefix)
