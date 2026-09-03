#!/usr/bin/env python3
"""Build a manifest for the local MMseqs2 homolog sequence database."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DB_PREFIX = AI_ROOT / "cache" / "mmseqs_databases" / "uniprot_sprot"
REPORT_OUT = AI_ROOT / "reports" / "mmseqs_homolog_database_report.json"
MANIFEST_OUT = AI_ROOT / "reports" / "mmseqs_homolog_database_manifest.json"
SMOKE_HITS = AI_ROOT / "tmp" / "mmseqs_download" / "example_sprot_hits.m8"

REQUIRED_SUFFIXES = ["", ".dbtype", ".index", ".lookup", ".source", ".version", "_h", "_h.dbtype", "_h.index"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_lines(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def run_probe(command: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=AI_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": "not_found"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "probe_timeout"}
    except OSError as exc:
        return {"returncode": 126, "stdout": "", "stderr": f"os_error:{exc}"}
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MMseqs homolog database manifest")
    parser.add_argument("--db-prefix", type=Path, default=DB_PREFIX)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--smoke-hits", type=Path, default=SMOKE_HITS)
    args = parser.parse_args()

    files = sorted(path for path in args.db_prefix.parent.glob(args.db_prefix.name + "*") if path.is_file()) if args.db_prefix.parent.exists() else []
    required_files = [Path(str(args.db_prefix) + suffix) for suffix in REQUIRED_SUFFIXES]
    missing_required = [rel(path) for path in required_files if not path.exists()]
    version_path = Path(str(args.db_prefix) + ".version")
    source_path = Path(str(args.db_prefix) + ".source")
    lookup_path = Path(str(args.db_prefix) + ".lookup")
    mmseqs = AI_ROOT / "cache" / "external" / "MMseqs2" / "bin" / "mmseqs"
    dbtype_probe = run_probe([str(mmseqs), "dbtype", str(args.db_prefix)]) if mmseqs.exists() else {"returncode": 127, "stdout": "", "stderr": "mmseqs_missing"}
    version_text = version_path.read_text(encoding="utf-8", errors="replace").strip() if version_path.exists() else ""
    smoke_hit_rows = count_lines(args.smoke_hits) or 0

    file_rows = [
        {
            "path": rel(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files
    ]
    ready = (
        not missing_required
        and dbtype_probe["returncode"] == 0
        and dbtype_probe["stdout"].strip() == "Aminoacid"
        and bool(version_text)
    )
    manifest = {
        "manifest_id": "kwb_mmseqs_homolog_database_manifest",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "database_name": "UniProtKB/Swiss-Prot",
        "database_prefix": rel(args.db_prefix),
        "database_version": version_text,
        "source": source_path.read_text(encoding="utf-8", errors="replace").strip() if source_path.exists() else "",
        "dbtype": dbtype_probe["stdout"].strip(),
        "dbtype_probe": dbtype_probe,
        "sequence_rows_from_lookup": count_lines(lookup_path),
        "file_count": len(file_rows),
        "files": file_rows,
        "required_files_missing": missing_required,
        "smoke_hits": rel(args.smoke_hits),
        "smoke_hit_rows": smoke_hit_rows,
        "ready_as_homolog_database": ready,
        "safe_for_model_claim": False,
        "policy": "Homolog database evidence only. MSA/conservation features must be generated and validated separately before model use.",
    }
    report = {
        "created_at": manifest["created_at"],
        "local_only": True,
        "database_name": manifest["database_name"],
        "database_prefix": manifest["database_prefix"],
        "database_version": manifest["database_version"],
        "dbtype": manifest["dbtype"],
        "sequence_rows_from_lookup": manifest["sequence_rows_from_lookup"],
        "file_count": manifest["file_count"],
        "required_files_missing": missing_required,
        "smoke_hit_rows": smoke_hit_rows,
        "ready_as_homolog_database": ready,
        "ready_for_model_claim": False,
        "manifest": rel(args.manifest),
        "policy": manifest["policy"],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ready_as_homolog_database": ready,
        "database_name": report["database_name"],
        "sequence_rows_from_lookup": report["sequence_rows_from_lookup"],
        "smoke_hit_rows": smoke_hit_rows,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
