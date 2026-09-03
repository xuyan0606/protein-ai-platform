#!/usr/bin/env python3
"""Resolve the active local ddG backend configuration."""

from __future__ import annotations

from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = AI_ROOT / "config" / "ddg_backend.local.json"
EXAMPLE_CONFIG = AI_ROOT / "config" / "ddg_backend.local.example.json"


def default_ddg_config_path() -> Path:
    return LOCAL_CONFIG if LOCAL_CONFIG.exists() else EXAMPLE_CONFIG


def ddg_config_display_name(path: Path | None = None) -> str:
    config = path or default_ddg_config_path()
    try:
        return str(config.relative_to(AI_ROOT))
    except ValueError:
        return str(config)
