#!/usr/bin/env python3
"""Build a local FoldX BuildModel parser contract using a static fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foldx_buildmodel_parser import parse_buildmodel_output


AI_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = AI_ROOT / "cache" / "advanced_features" / "ddg_physical_smoke" / "foldx_parser_contract_fixture"
REPORT = AI_ROOT / "reports" / "foldx_buildmodel_parser_contract_report.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def write_fixture(fixture_dir: Path) -> list[Path]:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    dif = fixture_dir / "Dif_10MH_A_T10A.fxout"
    average = fixture_dir / "Average_10MH_A_T10A.fxout"
    raw = fixture_dir / "Raw_10MH_A_T10A.fxout"
    dif.write_text(
        "FoldX 5.1 (2011)\n"
        "PDB file analysed: batch\n"
        "Output type: BuildModel\n"
        "Pdb\ttotal energy\tBackbone Hbond\tSidechain Hbond\n"
        "10MH_A_T10A_0.pdb\t-1.234\t0.100\t-0.200\n",
        encoding="utf-8",
    )
    average.write_text(
        "FoldX 5.1 (2011)\n"
        "PDB file analysed: batch\n"
        "Output type: BuildModel\n"
        "Pdb\ttotal energy\tBackbone Hbond\tSidechain Hbond\n"
        "10MH_A_T10A_AVG.pdb\t-1.200\t0.080\t-0.210\n",
        encoding="utf-8",
    )
    raw.write_text(
        "FoldX 5.1 (2011)\n"
        "PDB file analysed: batch\n"
        "Output type: BuildModel\n"
        "Pdb\ttotal energy\tBackbone Hbond\tSidechain Hbond\n"
        "10MH_A_T10A_RAW.pdb\t-1.180\t0.090\t-0.220\n",
        encoding="utf-8",
    )
    return [dif, average, raw]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FoldX BuildModel parser contract")
    parser.add_argument("--fixture-dir", type=Path, default=FIXTURE_DIR)
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()

    fixture_files = write_fixture(args.fixture_dir)
    mutation_context: dict[str, Any] = {
        "chain_id": "A",
        "pdb_position": 10,
        "wild_type": "T",
        "mutant": "A",
    }
    table = parse_buildmodel_output(args.fixture_dir, mutation_context)
    rows = table.get("rows") or []
    first_ddg = rows[0].get("ddg_kcal_mol") if rows else None
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "fixture_dir": rel(args.fixture_dir),
        "fixture_files": [
            {"path": rel(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}
            for path in fixture_files
        ],
        "parser_contract_ready": table.get("parse_status") == "parsed" and len(rows) == 1,
        "parse_status": table.get("parse_status"),
        "parsed_rows": len(rows),
        "source_family_counts": table.get("source_family_counts"),
        "first_ddg_kcal_mol": first_ddg,
        "negative_ddg_is_stabilizing": table.get("negative_ddg_is_stabilizing") is True,
        "foldx_runtime_ready": False,
        "foldx_executable_found": False,
        "training_import_written_rows": 0,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Parser contract only. It proves FoldX BuildModel output ingestion logic against a static fixture; it is not a FoldX install, license, runtime smoke, or training-label receipt.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "parser_contract_ready": report["parser_contract_ready"],
        "parsed_rows": report["parsed_rows"],
        "first_ddg_kcal_mol": report["first_ddg_kcal_mol"],
        "foldx_runtime_ready": report["foldx_runtime_ready"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
