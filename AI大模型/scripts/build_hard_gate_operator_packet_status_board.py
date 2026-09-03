#!/usr/bin/env python3
"""Build a fail-closed board for all top-tier hard-gate operator packets."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "hard_gate_operator_packet_status_board.json"
MD_OUT = AI_ROOT / "reports" / "hard_gate_operator_packet_status_board.md"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "hard_gate_operator_packet_status_board.jsonl"


GATES = [
    {
        "gate_id": "reviewed_numbering_real_labels",
        "gate_name": "Reviewed numbering + real labels",
        "packet_report": "reports/numbering_hard_gate_operator_packet_report.json",
        "validation_report": "reports/numbering_hard_gate_operator_packet_validation_report.json",
        "packet_jsonl": "datasets/governance/numbering_hard_gate_operator_packets.jsonl",
        "status_jsonl": "datasets/governance/numbering_hard_gate_operator_packet_status.jsonl",
    },
    {
        "gate_id": "wet_lab_training_eligible_feedback",
        "gate_name": "Wet-lab training-eligible feedback",
        "packet_report": "reports/wet_lab_hard_gate_operator_packet_report.json",
        "validation_report": "reports/wet_lab_hard_gate_operator_packet_validation_report.json",
        "packet_jsonl": "datasets/feedback/wet_lab_hard_gate_operator_packets.jsonl",
        "status_jsonl": None,
    },
    {
        "gate_id": "benchmark_scorecard_claim_cache",
        "gate_name": "Benchmark scorecard claim cache",
        "packet_report": "reports/benchmark_hard_gate_operator_packet_report.json",
        "validation_report": "reports/benchmark_hard_gate_operator_packet_validation_report.json",
        "packet_jsonl": "datasets/governance/benchmark_hard_gate_operator_packets.jsonl",
        "status_jsonl": None,
    },
    {
        "gate_id": "physical_ddg_runtime",
        "gate_name": "Rosetta/PyRosetta/FoldX physical ddG runtime",
        "packet_report": "reports/ddg_physical_runtime_receipt_preflight_report.json",
        "validation_report": "reports/ddg_physical_runtime_receipt_preflight_validation_report.json",
        "packet_jsonl": "datasets/governance/ddg_physical_runtime_receipt_preflight.jsonl",
        "status_jsonl": None,
    },
    {
        "gate_id": "substrate_fit_label_source",
        "gate_name": "Substrate-fit label/source",
        "packet_report": "reports/substrate_fit_hard_gate_operator_packet_report.json",
        "validation_report": "reports/substrate_fit_hard_gate_operator_packet_validation_report.json",
        "packet_jsonl": "datasets/governance/substrate_fit_hard_gate_operator_packets.jsonl",
        "status_jsonl": "datasets/governance/substrate_fit_hard_gate_operator_packet_status.jsonl",
    },
    {
        "gate_id": "structure_feature_expansion",
        "gate_name": "Structure feature expansion",
        "packet_report": "reports/structure_feature_hard_gate_operator_packet_report.json",
        "validation_report": "reports/structure_feature_hard_gate_operator_packet_validation_report.json",
        "packet_jsonl": "datasets/governance/structure_feature_hard_gate_operator_packets.jsonl",
        "status_jsonl": "datasets/governance/structure_feature_hard_gate_operator_packet_status.jsonl",
    },
]


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(rel: str | None, errors: list[str], required: bool = True) -> dict[str, Any]:
    if rel is None:
        return {}
    path = AI_ROOT / rel
    if not path.exists():
        if required:
            errors.append(f"missing_input:{rel}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"invalid_json:{rel}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"invalid_json_object:{rel}")
        return {}
    return data


def jsonl_rows(rel: str | None, errors: list[str], required: bool = True) -> int:
    if rel is None:
        return 0
    path = AI_ROOT / rel
    if not path.exists():
        if required:
            errors.append(f"missing_input:{rel}")
        return 0
    rows = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"invalid_jsonl:{rel}:{line_number}")
            continue
        rows += 1
    return rows


def first_int(report: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = report.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, dict):
            continue
    summary = report.get("summary")
    if isinstance(summary, dict):
        for key in keys:
            value = summary.get(key)
            if isinstance(value, int):
                return value
    return 0


def is_false(report: dict[str, Any], key: str) -> bool:
    value = report.get(key)
    if value is False:
        return True
    summary = report.get("summary")
    return isinstance(summary, dict) and summary.get(key) is False


def gate_row(gate: dict[str, Any], created_at: str) -> dict[str, Any]:
    errors: list[str] = []
    report = load_json(gate["packet_report"], errors)
    validation = load_json(gate.get("validation_report"), errors, required=False)
    packet_rows_from_jsonl = jsonl_rows(gate.get("packet_jsonl"), errors)
    status_rows_from_jsonl = jsonl_rows(gate.get("status_jsonl"), errors, required=False)

    packet_rows = first_int(
        report,
        "packet_rows",
        "physical_backend_rows",
        "preflight_rows",
        "backend_rows",
    )
    completion_ready_rows = first_int(
        report,
        "completion_ready_rows",
        "ready_to_write_formal_runtime_receipt_rows",
    )
    validation_present = bool(validation)
    all_valid = validation.get("all_operator_packets_valid")
    if all_valid is None and validation_present:
        all_valid = validation.get("all_rows_valid")
    if all_valid is None and validation_present:
        all_valid = validation.get("contract_valid")
    if all_valid is None and validation_present:
        all_valid = validation.get("success")
    if all_valid is None and not validation_present:
        all_valid = False

    row_errors = list(errors)
    if packet_rows != packet_rows_from_jsonl:
        row_errors.append(f"packet_report_jsonl_count_mismatch:{packet_rows}!={packet_rows_from_jsonl}")
    if report.get("safe_for_model_claim") is not False:
        row_errors.append("packet_report_safe_for_model_claim_not_false")
    if report.get("release_ready") is not False:
        row_errors.append("packet_report_release_ready_not_false")
    if gate["gate_id"] != "physical_ddg_runtime" and completion_ready_rows != 0:
        row_errors.append(f"completion_ready_rows_not_zero:{completion_ready_rows}")
    if validation_present and all_valid is not True:
        row_errors.append("validation_report_not_all_valid")

    return {
        "gate_id": gate["gate_id"],
        "gate_name": gate["gate_name"],
        "created_at": created_at,
        "status": "open_blocked",
        "packet_report": gate["packet_report"],
        "packet_jsonl": gate.get("packet_jsonl"),
        "packet_report_present": bool(report),
        "packet_rows": packet_rows,
        "packet_rows_from_jsonl": packet_rows_from_jsonl,
        "validation_report": gate.get("validation_report"),
        "validation_report_present": validation_present,
        "validation_status": "validated" if validation_present and all_valid is True and not row_errors else ("validation_pending" if not validation_present else "invalid"),
        "status_jsonl": gate.get("status_jsonl"),
        "status_rows_from_jsonl": status_rows_from_jsonl,
        "completion_ready_rows": 0,
        "training_unlocked": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "errors": row_errors,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Hard-Gate Operator Packet Status Board",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This board checks whether every top-tier hard gate has an auditable operator packet layer. It does not close any gate.",
        "",
        "## Summary",
        "",
        f"- Gate rows: {report['gate_rows']}",
        f"- Packet rows: {report['packet_rows']}",
        f"- Validated gates: {report['validated_gates']}",
        f"- Validation pending gates: {report['validation_pending_gates']}",
        f"- Invalid gates: {report['invalid_gates']}",
        f"- Completion ready rows: {report['completion_ready_rows']}",
        f"- Safe for model claim: {str(report['safe_for_model_claim']).lower()}",
        "",
        "## Gates",
        "",
        "| gate | packets | validation | errors |",
        "|---|---:|---|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['gate_name']} | {row['packet_rows']} | {row['validation_status']} | {len(row['errors'])} |"
        )
    lines.extend([
        "",
        "## Fail-Closed Boundary",
        "",
        "A validated packet means the operator work package is internally consistent. It is not an approval, a reviewed decision, a training label, a runtime receipt, or a release gate.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build hard-gate operator packet status board")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown", type=Path, default=MD_OUT)
    parser.add_argument("--jsonl", type=Path, default=JSONL_OUT)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    rows = [gate_row(gate, created_at) for gate in GATES]
    validation_counts: dict[str, int] = {}
    for row in rows:
        validation_counts[row["validation_status"]] = validation_counts.get(row["validation_status"], 0) + 1
    report = {
        "created_at": created_at,
        "local_only": True,
        "status": "blocked",
        "outputs": {
            "jsonl": relative(args.jsonl),
            "report": relative(args.output),
            "markdown": relative(args.markdown),
        },
        "gate_rows": len(rows),
        "packet_rows": sum(int(row["packet_rows"]) for row in rows),
        "validated_gates": validation_counts.get("validated", 0),
        "validation_pending_gates": validation_counts.get("validation_pending", 0),
        "invalid_gates": validation_counts.get("invalid", 0),
        "gate_validation_counts": dict(sorted(validation_counts.items())),
        "completion_ready_rows": 0,
        "training_unlocked": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "rows": rows,
    }
    write_jsonl(args.jsonl, rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(report, rows), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "gate_rows": report["gate_rows"],
        "packet_rows": report["packet_rows"],
        "validated_gates": report["validated_gates"],
        "validation_pending_gates": report["validation_pending_gates"],
        "invalid_gates": report["invalid_gates"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": relative(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
