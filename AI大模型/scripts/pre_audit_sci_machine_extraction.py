#!/usr/bin/env python3
"""First-pass, non-authoritative audit of SCI table extraction candidates."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports" / "sci_machine_extraction_candidates_20260902.jsonl"
DEFAULT_OUTPUT = ROOT / "reports" / "sci_machine_extraction_pre_audit_20260902.jsonl"

NUMBER_RE = re.compile(r"(?<![A-Za-z])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
MUTATION_RE = re.compile(r"\b[A-Z][0-9]{1,4}[A-Z*]\b|\b(?:wild[ -]?type|mutant|variant|construct)\b", re.I)
MEASUREMENT_RE = re.compile(r"\b(?:kcat|km|kcat/km|tm|half[ -]?life|activity|stability|yield|affinity|rate|turnover)\b", re.I)
UNIT_RE = re.compile(r"(?:s\s*\^?[-−]?1|sec(?:ond)?s?|min(?:ute)?s?|h(?:our)?s?|°?c|k(?:da)?|mm|μ?m|nm|mg|ml|%|fold|u/ml)", re.I)


def audit_row(row: dict) -> dict:
    cells = row.get("cells") or []
    texts = [str(cell).strip() for cell in cells]
    joined = " | ".join(texts)
    signals: list[str] = []
    if MUTATION_RE.search(joined):
        signals.append("construct_or_variant")
    if MEASUREMENT_RE.search(joined):
        signals.append("measurement_term")
    if NUMBER_RE.search(joined):
        signals.append("numeric_value")
    if UNIT_RE.search(joined):
        signals.append("unit")

    risks: list[str] = []
    if not texts or all(not text for text in texts):
        risks.append("empty_cells")
    if len(texts) < 2:
        risks.append("insufficient_columns")
    if not signals:
        risks.append("no_measurement_signal")
    if "numeric_value" in signals and "unit" not in signals:
        risks.append("unit_not_detected")
    if "construct_or_variant" not in signals:
        risks.append("construct_not_detected")

    if "empty_cells" in risks:
        status = "insufficient_evidence"
    elif {"numeric_value", "measurement_term"}.issubset(signals):
        status = "precheck_candidate"
    else:
        status = "needs_human_verification"

    return {
        "pmcid": row.get("pmcid", ""),
        "table_locator": row.get("table_locator", ""),
        "cells": cells,
        "source_status": row.get("status", ""),
        "pre_audit_status": status,
        "evidence_signals": signals,
        "risk_flags": risks,
        "human_verification_required": True,
        "formal_decision": None,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def run(input_path: Path, output_path: Path) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    counts = {"precheck_candidate": 0, "needs_human_verification": 0, "insufficient_evidence": 0}
    with input_path.open(encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as target:
        for line in source:
            if not line.strip():
                continue
            audited = audit_row(json.loads(line))
            target.write(json.dumps(audited, ensure_ascii=False) + "\n")
            count += 1
            counts[audited["pre_audit_status"]] += 1
    summary = {
        "input_rows": count,
        "status_counts": counts,
        "output": str(output_path),
        "formal_intake_authorized": False,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run(args.input, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
