#!/usr/bin/env python3
"""Build a local MSA execution plan without fabricating conservation data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
TARGETS = AI_ROOT / "datasets" / "curation" / "msa_conservation_targets.jsonl"
EXECUTOR_REPORT = AI_ROOT / "reports" / "msa_executor_readiness_report.json"
RUNTIME_REPORT = AI_ROOT / "reports" / "msa_runtime_readiness_report.json"
OUT = AI_ROOT / "datasets" / "curation" / "msa_execution_plan.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "msa_execution_plan_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MSA execution plan")
    parser.add_argument("--targets", type=Path, default=TARGETS)
    parser.add_argument("--executor-report", type=Path, default=EXECUTOR_REPORT)
    parser.add_argument("--runtime-report", type=Path, default=RUNTIME_REPORT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    targets = load_jsonl(args.targets)
    executor = load_json(args.executor_report)
    runtime = load_json(args.runtime_report)
    available = executor.get("available_executors") or []
    executor_name = available[0]["name"] if available else runtime.get("selected_runtime")
    runtime_ready = bool(available or runtime.get("runtime_ready"))

    rows = []
    for index, target in enumerate(targets, start=1):
        uniprot_id = target.get("uniprot_id")
        rows.append({
            "job_id": f"msa_job_{index:04d}",
            "uniprot_id": uniprot_id,
            "sequence_length": target.get("sequence_length"),
            "input_fasta": "datasets/curation/msa_inputs/msa_targets.fasta",
            "planned_msa_path": f"cache/msa/{uniprot_id}.aln.fasta" if uniprot_id else None,
            "planned_conservation_path": f"datasets/curation/msa_conservation/{uniprot_id}.conservation.json" if uniprot_id else None,
            "executor": executor_name,
            "status": "ready_for_execution" if runtime_ready else "blocked_no_executor_or_runtime",
            "policy": "execution plan only; no MSA/conservation values generated here",
        })
    write_jsonl(args.output, rows)
    report = {
        "target_rows": len(targets),
        "planned_jobs": len(rows),
        "ready_jobs": sum(1 for row in rows if row["status"] == "ready_for_execution"),
        "blocked_jobs": sum(1 for row in rows if row["status"] != "ready_for_execution"),
        "executor_status": executor.get("executor_status"),
        "available_executors": available,
        "runtime_ready": runtime.get("runtime_ready"),
        "selected_runtime": runtime.get("selected_runtime"),
        "runtime_blockers": runtime.get("blockers"),
        "output": str(args.output),
        "policy": "MSA remains blocked until a real executor and homolog source/cache are configured",
        "local_install_options": [
            "Install MAFFT or Clustal Omega locally and provide a homolog FASTA source per target.",
            "Install MMseqs2 or Foldseek locally for database-backed homolog retrieval.",
            "Use a precomputed trusted MSA/conservation cache and point targets to those files.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "planned_jobs": report["planned_jobs"],
        "ready_jobs": report["ready_jobs"],
        "blocked_jobs": report["blocked_jobs"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
