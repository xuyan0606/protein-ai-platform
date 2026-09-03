#!/usr/bin/env python3
"""Build real local FASTA inputs for MSA/conservation execution."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "backend" / "protein_ai.db"
TARGETS = AI_ROOT / "datasets" / "curation" / "msa_conservation_targets.jsonl"
FASTA_OUT = AI_ROOT / "datasets" / "curation" / "msa_inputs" / "msa_targets.fasta"
MANIFEST_OUT = AI_ROOT / "reports" / "msa_input_manifest.json"
READINESS_OUT = AI_ROOT / "reports" / "msa_executor_readiness_report.json"
MSA_RUNTIME_CONFIG = AI_ROOT / "config" / "msa_runtime.local.example.json"
EXECUTOR_NAMES = ["mmseqs", "mafft", "clustalo", "hhblits", "jackhmmer", "foldseek"]


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def wrap(sequence: str, width: int = 80) -> str:
    return "\n".join(sequence[index:index + width] for index in range(0, len(sequence), width))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MSA FASTA inputs")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--targets", type=Path, default=TARGETS)
    parser.add_argument("--fasta-output", type=Path, default=FASTA_OUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--report", type=Path, default=READINESS_OUT)
    args = parser.parse_args()

    targets = load_jsonl(args.targets)
    ids = [row.get("uniprot_id") for row in targets if row.get("uniprot_id")]
    placeholders = ",".join("?" for _ in ids)
    with connect_ro(args.db) as conn:
        sequences = {
            row[0]: row[1]
            for row in conn.execute(
                f"SELECT uniprot_id, sequence FROM enzyme_records WHERE uniprot_id IN ({placeholders})",
                ids,
            ).fetchall()
        } if ids else {}
    fasta_rows = []
    missing = []
    manifest_rows = []
    for target in targets:
        uniprot_id = target.get("uniprot_id")
        sequence = sequences.get(uniprot_id)
        if not sequence:
            missing.append(uniprot_id)
            continue
        fasta_rows.append(f">{uniprot_id}\n{wrap(sequence)}")
        manifest_rows.append({
            "uniprot_id": uniprot_id,
            "sequence_length": len(sequence),
            "fasta_status": "ready",
            "msa_status": "missing",
            "conservation_status": "missing",
        })
    args.fasta_output.parent.mkdir(parents=True, exist_ok=True)
    args.fasta_output.write_text("\n".join(fasta_rows) + ("\n" if fasta_rows else ""), encoding="utf-8")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps({
        "local_only": True,
        "fasta": str(args.fasta_output),
        "targets": manifest_rows,
        "missing_sequence_targets": missing,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    available_executors = [
        {"name": name, "path": shutil.which(name)}
        for name in EXECUTOR_NAMES
        if shutil.which(name)
    ]
    runtime_config = load_json(MSA_RUNTIME_CONFIG)
    configured_binary = (runtime_config.get("local_binary") or {}).get("binary_path")
    if configured_binary:
        binary_path = Path(configured_binary)
        if not binary_path.is_absolute():
            binary_path = AI_ROOT / binary_path
        if binary_path.exists():
            available_executors.append({
                "name": "configured_mmseqs2_local_binary",
                "path": str(binary_path),
            })
    seen_paths: set[str] = set()
    deduped_executors: list[dict[str, str]] = []
    for executor in available_executors:
        path = str(executor.get("path") or "")
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        deduped_executors.append(executor)
    report = {
        "target_rows": len(targets),
        "fasta_ready": len(manifest_rows),
        "missing_sequences": len(missing),
        "msa_present": 0,
        "conservation_present": 0,
        "executor_status": "available" if deduped_executors else "unavailable",
        "available_executors": deduped_executors,
        "ready": False,
        "policy": "FASTA inputs are real local sequences; no MSA or conservation values are fabricated",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "target_rows": report["target_rows"],
        "fasta_ready": report["fasta_ready"],
        "missing_sequences": report["missing_sequences"],
        "ready": report["ready"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
