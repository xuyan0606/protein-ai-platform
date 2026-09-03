#!/usr/bin/env python3
"""Shared Python module discovery helpers for local ddG runtimes."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON_TARGETS = [
    AI_ROOT / "cache" / "external" / "PyRosetta" / "python",
]


def resolve_module_path(value: Any) -> Path | None:
    if isinstance(value, Path):
        path = value
    elif isinstance(value, str) and value:
        path = Path(value)
    else:
        return None
    return path if path.is_absolute() else AI_ROOT / path


def existing_search_paths(extra_paths: list[Any] | None = None) -> list[Path]:
    paths: list[Path] = []
    for value in [*(extra_paths or []), *LOCAL_PYTHON_TARGETS]:
        path = resolve_module_path(value)
        if path is not None and path.exists() and path.is_dir() and path not in paths:
            paths.append(path)
    return paths


def find_module_spec(module: str, extra_paths: list[Any] | None = None) -> tuple[Any, str | None, str | None]:
    try:
        spec = importlib.util.find_spec(module)
    except (AttributeError, ImportError, ValueError) as exc:
        spec = None
        error = str(exc)
    else:
        error = None
    if spec is not None:
        return spec, "sys_path", error

    for path in existing_search_paths(extra_paths):
        try:
            spec = importlib.machinery.PathFinder.find_spec(module, [str(path)])
        except (AttributeError, ImportError, ValueError) as exc:
            error = str(exc)
            continue
        if spec is not None:
            return spec, str(path), error
    return None, None, error


def module_probe_row(module: str, extra_paths: list[Any] | None = None) -> dict[str, Any]:
    spec, discovered_via, error = find_module_spec(module, extra_paths)
    return {
        "module": module,
        "available": spec is not None,
        "origin": getattr(spec, "origin", None) if spec is not None else None,
        "discovered_via": discovered_via,
        "local_search_paths": [str(path) for path in existing_search_paths(extra_paths)],
        "error": error,
        "python_executable": sys.executable,
        "module_imported": False,
        "ddg_protocol_executed": False,
    }


def module_available(module: str, extra_paths: list[Any] | None = None) -> bool:
    spec, _, _ = find_module_spec(module, extra_paths)
    return spec is not None


def add_local_module_paths(extra_paths: list[Any] | None = None) -> list[str]:
    added: list[str] = []
    for path in existing_search_paths(extra_paths):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
            added.append(value)
    return added
