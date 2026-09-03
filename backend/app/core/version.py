"""Project version helpers."""

from __future__ import annotations

from pathlib import Path


DEFAULT_VERSION = "0.1.0"


def get_project_version() -> str:
    """Read the repo-root VERSION file, falling back to the current release."""
    version_file = Path(__file__).resolve().parents[3] / "VERSION"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return DEFAULT_VERSION
    return version or DEFAULT_VERSION


PROJECT_VERSION = get_project_version()
