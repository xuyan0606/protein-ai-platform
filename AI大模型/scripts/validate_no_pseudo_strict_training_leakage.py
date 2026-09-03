#!/usr/bin/env python3
"""Fail closed if trained artifacts leak while strict real-source rows are zero."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_TABLE = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_supervised_repaired_verified.jsonl"
STRICT_MSA_TABLE = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_strict_msa_site_features.jsonl"
REPAIRED_REPORT = AI_ROOT / "reports" / "repaired_supervised_table_report.json"
LABEL_PROVENANCE = AI_ROOT / "reports" / "label_provenance_audit_report.json"
ARTIFACTS = [
    AI_ROOT / "reports" / "repaired_supervised_baseline_eval.json",
    AI_ROOT / "prototype" / "repaired_supervised_baseline_model.json",
    AI_ROOT / "reports" / "repaired_supervised_msa_baseline_eval.json",
    AI_ROOT / "prototype" / "repaired_supervised_msa_baseline_model.json",
]
OUT = AI_ROOT / "reports" / "no_pseudo_strict_training_leakage_validation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def split_rows(report: dict[str, Any]) -> int:
    splits = report.get("splits") if isinstance(report.get("splits"), dict) else {}
    return sum(int((row or {}).get("rows") or 0) for row in splits.values() if isinstance(row, dict))


def positive_training_count(artifact: dict[str, Any]) -> int:
    candidates = [
        artifact.get("trained_on_rows"),
        artifact.get("train_rows"),
        artifact.get("training_rows"),
        artifact.get("rows") if artifact.get("status") != "blocked_empty_train_split" else 0,
        split_rows(artifact),
    ]
    return max(int(value or 0) for value in candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate no pseudo strict training leakage")
    parser.add_argument("--strict-table", type=Path, default=STRICT_TABLE)
    parser.add_argument("--strict-msa-table", type=Path, default=STRICT_MSA_TABLE)
    parser.add_argument("--repaired-report", type=Path, default=REPAIRED_REPORT)
    parser.add_argument("--label-provenance", type=Path, default=LABEL_PROVENANCE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    strict_rows = count_jsonl(args.strict_table)
    strict_msa_rows = count_jsonl(args.strict_msa_table)
    repaired = load_json(args.repaired_report)
    provenance = load_json(args.label_provenance)
    failures: list[str] = []
    warnings: list[str] = []
    artifact_rows = []

    if int(repaired.get("supervised_rows") or 0) != strict_rows:
        failures.append("repaired_report_supervised_rows_mismatch")
    if int(provenance.get("strict_rows") or 0) != strict_rows:
        failures.append("label_provenance_strict_rows_mismatch")
    if strict_rows == 0 and strict_msa_rows != 0:
        failures.append("strict_msa_features_present_when_strict_rows_zero")

    for path in ARTIFACTS:
        artifact = load_json(path)
        rel = str(path.relative_to(AI_ROOT))
        if not artifact:
            failures.append(f"missing_artifact:{rel}")
            artifact_rows.append({"path": rel, "exists": False, "valid": False})
            continue
        positive_rows = positive_training_count(artifact)
        status = artifact.get("status")
        safe_for_model_claim = artifact.get("safe_for_model_claim")
        row_failures = []
        if strict_rows == 0 and positive_rows:
            row_failures.append(f"positive_training_rows_when_strict_rows_zero:{positive_rows}")
        if strict_rows == 0 and status != "blocked_empty_train_split":
            row_failures.append(f"status_not_blocked_empty_train_split:{status}")
        if safe_for_model_claim is not False:
            row_failures.append("safe_for_model_claim_not_false")
        failures.extend(f"{rel}:{failure}" for failure in row_failures)
        artifact_rows.append({
            "path": rel,
            "exists": True,
            "status": status,
            "positive_training_count": positive_rows,
            "safe_for_model_claim": safe_for_model_claim,
            "valid": not row_failures,
            "failures": row_failures,
        })

    if strict_rows == 0:
        warnings.append("strict_real_source_supervised_rows_zero_training_must_remain_blocked")

    report = {
        "strict_table": str(args.strict_table),
        "strict_rows": strict_rows,
        "strict_msa_rows": strict_msa_rows,
        "claim_eligible_rows": int(provenance.get("claim_eligible_rows") or 0),
        "source_rejected_by_deep_audit_rows": int(repaired.get("source_rejected_by_deep_audit_rows") or 0),
        "artifact_count": len(artifact_rows),
        "valid_artifacts": sum(1 for row in artifact_rows if row.get("valid")),
        "invalid_artifacts": sum(1 for row in artifact_rows if not row.get("valid")),
        "failures": failures,
        "warnings": warnings,
        "safe_for_training_pipeline": not failures,
        "safe_for_model_claim": False,
        "release_ready": False,
        "artifacts": artifact_rows,
        "policy": (
            "When strict real-source supervised rows are zero, supervised training artifacts must be blocked_empty_train_split "
            "with zero trained rows and safe_for_model_claim=false."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "strict_rows": strict_rows,
        "invalid_artifacts": report["invalid_artifacts"],
        "failures": len(failures),
        "safe_for_training_pipeline": report["safe_for_training_pipeline"],
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
