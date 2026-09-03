#!/usr/bin/env python3
"""Import reviewed Venus-15B amylase wet-lab observation into feedback intake.

The project owner stated this folder is a real experiment source. This script
still keeps the intake auditable: it verifies mutation numbering against the
15B sequence and records source file checksums instead of inventing numeric
assay values that are not present in the source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = AI_ROOT / "Venus-15B淀粉酶项目"
LOCAL_FEEDBACK = AI_ROOT / "datasets" / "feedback" / "experiment_feedback.local.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "venus15b_feedback_import_report.json"

SEQUENCE_FILE = "淀粉酶15B序列.txt"
BACKGROUND_FILE = "淀粉酶背景.txt"
STRUCTURE_FILE = "15B-AAP-noCa.pdb"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def verify_mutation(sequence: str, mutation: str) -> tuple[bool, str | None]:
    wt = mutation[0]
    position = int(mutation[1:-1])
    if position < 1 or position > len(sequence):
        return False, None
    observed = sequence[position - 1]
    return observed == wt, observed


def build_feedback(project_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    sequence_path = project_dir / SEQUENCE_FILE
    background_path = project_dir / BACKGROUND_FILE
    structure_path = project_dir / STRUCTURE_FILE
    sequence = sequence_path.read_text(encoding="utf-8").strip()
    background = background_path.read_text(encoding="utf-8")

    mutation = "E331Q"
    numbering_ok, observed = verify_mutation(sequence, mutation)
    evidence_phrase_present = all(token in background for token in ["E331Q", "pH4.5", "pH6.0", "活性比值"])

    feedback = {
        "feedback_id": "venus15b-e331q-ph45-ph60-ratio-observation-001",
        "enzyme_id": "Venus-15B-alpha-amylase-AAP-noCa",
        "uniprot_id": None,
        "project_id": "venus-15b",
        "mutation": mutation,
        "canonical_position": 331,
        "numbering_verified": bool(numbering_ok),
        "assay_type": "activity",
        "assay_condition": {
            "ph": 4.5,
            "temperature_c": None,
            "buffer": None,
            "substrate": "starch",
            "expression_system": None,
            "comparison_condition": {"ph": 6.0},
            "metric": "pH4.5/pH6.0 activity ratio",
        },
        "outcome": "go" if numbering_ok and evidence_phrase_present else "inconclusive",
        "data_granularity": "qualitative_historical_observation",
        "quantitative_assay_available": False,
        "plate_level_available": False,
        "activity_relative_to_wt": None,
        "stability_delta_tm_c": None,
        "expression_yield_relative": None,
        "notes": (
            "User-designated real Venus-15B experiment source. Background states prior experiment observed "
            "E331Q improves pH4.5/pH6.0 activity ratio. Numeric activity, replicate count, raw plate signal "
            "and QC are not present in the source folder, so numeric fields remain null."
        ),
        "source": "kwb_historical",
        "recorded_at": "2026-07-06T09:35:58+08:00",
    }
    evidence = {
        "project_dir": str(project_dir),
        "sequence_file": str(sequence_path),
        "background_file": str(background_path),
        "structure_file": str(structure_path),
        "sequence_sha256": sha256(sequence_path),
        "background_sha256": sha256(background_path),
        "structure_sha256": sha256(structure_path),
        "sequence_length": len(sequence),
        "mutation": mutation,
        "numbering_verified": bool(numbering_ok),
        "observed_sequence_residue": observed,
        "evidence_phrase_present": evidence_phrase_present,
        "training_eligible_under_current_validator": bool(numbering_ok and evidence_phrase_present),
        "limitations": [
            "qualitative historical activity observation only",
            "no numeric activity ratio in source text",
            "no replicate/QC/raw plate table in source folder",
            "not plate-level training data",
        ],
    }
    return feedback, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Venus-15B feedback observation")
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--feedback", type=Path, default=LOCAL_FEEDBACK)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    feedback, evidence = build_feedback(args.project_dir)
    rows = load_jsonl(args.feedback)
    by_id = {row.get("feedback_id"): row for row in rows if row.get("feedback_id")}
    by_id[feedback["feedback_id"]] = feedback
    merged = sorted(by_id.values(), key=lambda row: str(row.get("feedback_id")))
    write_jsonl(args.feedback, merged)

    report = {
        "imported_feedback_id": feedback["feedback_id"],
        "feedback_rows_before": len(rows),
        "feedback_rows_after": len(merged),
        "new_or_updated": True,
        "evidence": evidence,
        "output": str(args.feedback),
        "safe_for_model_claim": False,
        "policy": "Imports one reviewed historical KWB feedback observation; does not create plate-level data or numeric assay values.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "feedback_rows_after": len(merged),
        "numbering_verified": evidence["numbering_verified"],
        "training_eligible_under_current_validator": evidence["training_eligible_under_current_validator"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
