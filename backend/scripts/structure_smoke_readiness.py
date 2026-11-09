#!/usr/bin/env python
"""Report whether structure smoke can run in demo or live mode.

This script is intentionally local-only. It does not probe remote endpoints or
download datasets; it only inspects configured paths and environment variables
so the operator can see which smoke mode is currently runnable.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_SIFTS_DIR = PROJECT_ROOT / "app" / "data" / "fixtures" / "structure_smoke"
ANNOTATION_SUFFIXES = (".json", ".csv", ".tsv")
DEMO_ANNOTATION_SOURCE_DB = "local_demo"
DEMO_SIFTS_FILENAMES = {"1abc.json"}


def _print_status(label: str, status: str, detail: str) -> None:
    print(f"{label}\t{status}\t{detail}")


def _existing_path(value: str) -> Path | None:
    if not value.strip():
        return None
    path = Path(value).expanduser()
    return path if path.exists() else None


def _directory_has_supported_files(path: Path, suffixes: tuple[str, ...]) -> bool:
    if path.is_file():
        return path.suffix.lower() in suffixes
    if not path.is_dir():
        return False
    return any(candidate.is_file() and candidate.suffix.lower() in suffixes for candidate in path.rglob("*"))


def _annotations_ready(path: Path | None) -> bool:
    if path is None:
        return False
    if path.is_file():
        return path.suffix.lower() in ANNOTATION_SUFFIXES
    if not path.is_dir():
        return False
    for stem in ("base", "interpro", "mcsa", "signalp"):
        for suffix in ANNOTATION_SUFFIXES:
            if (path / f"{stem}{suffix}").exists():
                return True
    return False


def _load_json(path: Path) -> dict[str, object] | list[object] | None:
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _annotations_status(path: Path | None) -> tuple[str, bool]:
    if not _annotations_ready(path):
        return "missing", False
    if path and path.is_dir():
        metadata = path / "metadata.json"
        payload = _load_json(metadata) if metadata.exists() else None
        if isinstance(payload, dict) and payload.get("default_source_db") == DEMO_ANNOTATION_SOURCE_DB:
            return "demo", False
    return "ready", True


def _sifts_status(path: Path | None) -> tuple[str, bool]:
    if not path or not _directory_has_supported_files(path, ANNOTATION_SUFFIXES):
        return "missing", False
    if path.is_file():
        if path.name in DEMO_SIFTS_FILENAMES:
            return "demo", False
        return "ready", True
    names = {
        candidate.name
        for candidate in path.rglob("*")
        if candidate.is_file() and candidate.suffix.lower() in ANNOTATION_SUFFIXES
    }
    if names and names.issubset(DEMO_SIFTS_FILENAMES):
        return "demo", False
    return "ready", True


def _resolve_foldseek_db() -> tuple[str, Path | None]:
    for name, value in (
        ("pdb", settings.FOLDSEEK_DATABASE_PDB),
        ("alphafold", settings.FOLDSEEK_DATABASE_ALPHAFOLD),
        ("custom", settings.FOLDSEEK_DATABASE_CUSTOM),
    ):
        path = _existing_path(value)
        if path is not None:
            return name, path

    root = _existing_path(settings.FOLDSEEK_DATABASE_ROOT)
    if root is None:
        return "", None

    for name in ("pdb", "alphafold", "custom"):
        candidate = root / name
        if candidate.exists():
            return name, candidate
    return "", root


def _resolve_binary(binary: str) -> str:
    value = (binary or "").strip()
    if not value:
        return ""
    if os.path.sep in value:
        path = Path(value).expanduser()
        return str(path) if path.exists() else value
    found = shutil.which(value)
    return found or value


def _path_has_usable_entries(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    if path.is_file():
        return True
    return any(candidate.is_file() for candidate in path.rglob("*"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Exit non-zero unless summary reaches live-ready.",
    )
    args = parser.parse_args()

    deploy_root = _existing_path(settings.DEPLOY_DATA_ROOT)
    _print_status(
        "deploy_data_root",
        "ready" if deploy_root is not None else "missing",
        str(deploy_root or settings.DEPLOY_DATA_ROOT or "DEPLOY_DATA_ROOT unset"),
    )

    demo_sifts_ready = DEMO_SIFTS_DIR.exists() and any(DEMO_SIFTS_DIR.glob("*.json"))
    _print_status(
        "demo_sifts",
        "ready" if demo_sifts_ready else "missing",
        str(DEMO_SIFTS_DIR),
    )

    sifts_path = _existing_path(settings.SIFTS_MAPPING_PATH)
    live_sifts_status, live_sifts_ready = _sifts_status(sifts_path)
    _print_status(
        "live_sifts",
        live_sifts_status,
        str(sifts_path or settings.SIFTS_MAPPING_PATH or "SIFTS_MAPPING_PATH unset"),
    )

    annotation_path = _existing_path(settings.LOCAL_ANNOTATION_FIXTURE_PATH)
    live_annotations_status, live_annotations_ready = _annotations_status(annotation_path)
    _print_status(
        "live_annotations",
        live_annotations_status,
        str(annotation_path or settings.LOCAL_ANNOTATION_FIXTURE_PATH or "LOCAL_ANNOTATION_FIXTURE_PATH unset"),
    )

    pdb_file = _existing_path(settings.STRUCTURE_SMOKE_PDB_FILE)
    _print_status(
        "live_query_pdb",
        "ready" if pdb_file is not None else "missing",
        str(pdb_file or settings.STRUCTURE_SMOKE_PDB_FILE or "STRUCTURE_SMOKE_PDB_FILE unset"),
    )

    endpoint = (settings.FOLDSEEK_API_URL or "").strip()
    if endpoint:
        _print_status("live_foldseek_http", "ready", endpoint)
    else:
        _print_status("live_foldseek_http", "missing", "FOLDSEEK_API_URL unset")

    binary_label = _resolve_binary(settings.FOLDSEEK_BINARY) or "FOLDSEEK_BINARY unset"
    db_name, db_path = _resolve_foldseek_db()
    # Reject common shell placeholders: they can satisfy an executable/path
    # check but cannot produce scientific Foldseek results.
    binary_basename = Path(binary_label).name.lower() if binary_label else ""
    placeholder_binary = binary_basename in {"echo", "true", "false", "printf"}
    foldseek_cli_ready = (
        bool(settings.FOLDSEEK_BINARY.strip())
        and not placeholder_binary
        and _path_has_usable_entries(db_path)
    )
    _print_status(
        "live_foldseek_cli",
        "ready" if foldseek_cli_ready else "missing",
        f"binary={binary_label}; database={db_name or 'unset'}:{db_path or settings.FOLDSEEK_DATABASE_ROOT or 'unset'}"
        + ("; placeholder_binary_rejected" if placeholder_binary else ""),
    )

    live_foldseek_ready = bool(endpoint) or foldseek_cli_ready
    live_ready = live_sifts_ready and live_annotations_ready and live_foldseek_ready and pdb_file is not None
    demo_ready = demo_sifts_ready

    print("")
    summary_status = "live-ready" if live_ready else "demo-ready" if demo_ready else "blocked"
    _print_status(
        "summary",
        summary_status,
        (
            "Run demo: SIFTS_SMOKE_USE_DEMO=1 FOLDSEEK_SMOKE_USE_DEMO=1 .venv/bin/python scripts/smoke_structure_data.py"
            if not live_ready
            else "Run live: .venv/bin/python scripts/smoke_structure_data.py"
        ),
    )
    if args.require_live and summary_status != "live-ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
