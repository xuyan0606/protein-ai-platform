#!/usr/bin/env python
"""Smoke test the real GROMACS pdb2gmx topology precheck path.

This script does not run MD. It only exercises the lightweight topology
validation layer used before submitting mutant structures to long MD tasks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.gromacs_md import _validate_pdb_topology


MINI_PDB = """\
ATOM      1  N   MET A 204      11.104  13.207   8.678  1.00 20.00           N
ATOM      2  CA  MET A 204      12.104  13.207   8.678  1.00 20.00           C
ATOM      3  C   MET A 204      12.504  14.607   8.678  1.00 20.00           C
ATOM      4  O   MET A 204      13.504  14.807   8.678  1.00 20.00           O
ATOM      5  CB  MET A 204      12.204  12.107   9.678  1.00 20.00           C
TER       6      MET A 204
END
"""

DEFAULT_SMOKE_PDB_CANDIDATES = (
    PROJECT_ROOT / "deploy_data" / "smoke" / "query.pdb",
    PROJECT_ROOT / "backend" / "388aa-SD-WT.pdb",
)


def _load_pdb_text(path: str | None) -> str:
    candidate = (path or os.getenv("MD_TOPOLOGY_SMOKE_PDB_FILE") or "").strip()
    if not candidate:
        for default_path in DEFAULT_SMOKE_PDB_CANDIDATES:
            if default_path.exists():
                return default_path.read_text(encoding="utf-8", errors="replace")
        return MINI_PDB
    return Path(candidate).read_text(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdb-file", default=None, help="Optional PDB file to validate. Defaults to an internal mini PDB.")
    parser.add_argument("--force-field", default=os.getenv("MD_TOPOLOGY_SMOKE_FORCE_FIELD", "amber99sb-ildn"))
    parser.add_argument("--water-model", default=os.getenv("MD_TOPOLOGY_SMOKE_WATER_MODEL", "tip3p"))
    parser.add_argument("--timeout-seconds", type=int, default=int(os.getenv("MD_TOPOLOGY_SMOKE_TIMEOUT_SECONDS", "120")))
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--require-live", action="store_true", help="Exit non-zero unless pdb2gmx validates successfully.")
    args = parser.parse_args()

    result = _validate_pdb_topology(
        _load_pdb_text(args.pdb_file),
        force_field=args.force_field,
        water_model=args.water_model,
        timeout=args.timeout_seconds,
    )
    payload = {
        "name": "md_topology_smoke",
        "summary": {
            "status": result.get("status"),
            "topology_validated": bool(result.get("topology_validated")),
            "safe_for_ranking": bool(result.get("safe_for_ranking")),
            "error_code": result.get("error_code"),
        },
        "result": result,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        summary = payload["summary"]
        print(
            "md_topology_smoke\t"
            f"status={summary['status']}\t"
            f"topology_validated={summary['topology_validated']}\t"
            f"safe_for_ranking={summary['safe_for_ranking']}\t"
            f"error_code={summary.get('error_code') or ''}"
        )

    if args.require_live and not result.get("topology_validated"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
