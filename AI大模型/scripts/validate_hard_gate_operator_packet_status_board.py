#!/usr/bin/env python3
"""Validate the hard-gate operator packet status board."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
REPORT = AI_ROOT / "reports" / "hard_gate_operator_packet_status_board.json"
MARKDOWN = AI_ROOT / "reports" / "hard_gate_operator_packet_status_board.md"
JSONL = AI_ROOT / "datasets" / "governance" / "hard_gate_operator_packet_status_board.jsonl"
OUTPUT = AI_ROOT / "reports" / "hard_gate_operator_packet_status_board_validation_report.json"

GATES = [
    ("reviewed_numbering_real_labels", "Reviewed numbering + real labels", "reports/numbering_hard_gate_operator_packet_report.json", "reports/numbering_hard_gate_operator_packet_validation_report.json", "datasets/governance/numbering_hard_gate_operator_packets.jsonl", "datasets/governance/numbering_hard_gate_operator_packet_status.jsonl"),
    ("wet_lab_training_eligible_feedback", "Wet-lab training-eligible feedback", "reports/wet_lab_hard_gate_operator_packet_report.json", "reports/wet_lab_hard_gate_operator_packet_validation_report.json", "datasets/feedback/wet_lab_hard_gate_operator_packets.jsonl", None),
    ("benchmark_scorecard_claim_cache", "Benchmark scorecard claim cache", "reports/benchmark_hard_gate_operator_packet_report.json", "reports/benchmark_hard_gate_operator_packet_validation_report.json", "datasets/governance/benchmark_hard_gate_operator_packets.jsonl", None),
    ("physical_ddg_runtime", "Rosetta/PyRosetta/FoldX physical ddG runtime", "reports/ddg_physical_runtime_receipt_preflight_report.json", "reports/ddg_physical_runtime_receipt_preflight_validation_report.json", "datasets/governance/ddg_physical_runtime_receipt_preflight.jsonl", None),
    ("substrate_fit_label_source", "Substrate-fit label/source", "reports/substrate_fit_hard_gate_operator_packet_report.json", "reports/substrate_fit_hard_gate_operator_packet_validation_report.json", "datasets/governance/substrate_fit_hard_gate_operator_packets.jsonl", "datasets/governance/substrate_fit_hard_gate_operator_packet_status.jsonl"),
    ("structure_feature_expansion", "Structure feature expansion", "reports/structure_feature_hard_gate_operator_packet_report.json", "reports/structure_feature_hard_gate_operator_packet_validation_report.json", "datasets/governance/structure_feature_hard_gate_operator_packets.jsonl", "datasets/governance/structure_feature_hard_gate_operator_packet_status.jsonl"),
]


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def check(condition: bool, failures: list[dict[str, Any]], name: str, observed: Any, expected: Any) -> None:
    if not condition:
        failures.append({"check": name, "observed": observed, "expected": expected})


def load_json(rel_or_path: str | Path, failures: list[dict[str, Any]], label: str, required: bool = True) -> dict[str, Any]:
    path = rel_or_path if isinstance(rel_or_path, Path) else AI_ROOT / rel_or_path
    if not path.exists():
        if required:
            failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append({"check": f"{label}_valid_json", "observed": str(exc), "expected": "JSON object"})
        return {}
    if not isinstance(value, dict):
        failures.append({"check": f"{label}_json_object", "observed": type(value).__name__, "expected": "object"})
        return {}
    return value


def load_jsonl(rel_or_path: str | Path | None, failures: list[dict[str, Any]], label: str, required: bool = True) -> list[dict[str, Any]]:
    if rel_or_path is None:
        return []
    path = rel_or_path if isinstance(rel_or_path, Path) else AI_ROOT / rel_or_path
    if not path.exists():
        if required:
            failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append({"check": f"{label}_valid_jsonl", "line": line_number, "observed": str(exc), "expected": "JSON object"})
            continue
        if not isinstance(value, dict):
            failures.append({"check": f"{label}_jsonl_object", "line": line_number, "observed": type(value).__name__, "expected": "object"})
            continue
        rows.append(value)
    return rows


def read_text(path: Path, failures: list[dict[str, Any]], label: str) -> str:
    if not path.exists():
        failures.append({"check": f"{label}_exists", "observed": "missing", "expected": relative(path)})
        return ""
    return path.read_text(encoding="utf-8")


def first_int(report: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = report.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    summary = report.get("summary")
    if isinstance(summary, dict):
        for key in keys:
            value = summary.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return 0


def validation_ok(validation: dict[str, Any]) -> bool:
    for key in ("all_operator_packets_valid", "all_rows_valid", "contract_valid", "success"):
        if key in validation:
            return validation.get(key) is True
    return False


def expected_rows(failures: list[dict[str, Any]], created_at: str) -> list[dict[str, Any]]:
    rows = []
    for gate_id, gate_name, packet_report_path, validation_path, packet_jsonl_path, status_jsonl_path in GATES:
        packet_report = load_json(packet_report_path, failures, f"{gate_id}_packet_report")
        validation = load_json(validation_path, failures, f"{gate_id}_validation_report")
        packet_jsonl = load_jsonl(packet_jsonl_path, failures, f"{gate_id}_packet_jsonl")
        status_jsonl = load_jsonl(status_jsonl_path, failures, f"{gate_id}_status_jsonl", required=False)
        packet_rows = first_int(packet_report, "packet_rows", "physical_backend_rows", "preflight_rows", "backend_rows")
        completion_rows = first_int(packet_report, "completion_ready_rows", "ready_to_write_formal_runtime_receipt_rows")
        errors = []
        if packet_rows != len(packet_jsonl):
            errors.append(f"packet_report_jsonl_count_mismatch:{packet_rows}!={len(packet_jsonl)}")
        if packet_report.get("safe_for_model_claim") is not False:
            errors.append("packet_report_safe_for_model_claim_not_false")
        if packet_report.get("release_ready") is not False:
            errors.append("packet_report_release_ready_not_false")
        if gate_id != "physical_ddg_runtime" and completion_rows != 0:
            errors.append(f"completion_ready_rows_not_zero:{completion_rows}")
        if validation_ok(validation) is not True:
            errors.append("validation_report_not_all_valid")
        status = "validated" if validation and validation_ok(validation) and not errors else "invalid"
        rows.append({
            "gate_id": gate_id,
            "gate_name": gate_name,
            "created_at": created_at,
            "status": "open_blocked",
            "packet_report": packet_report_path,
            "packet_jsonl": packet_jsonl_path,
            "packet_report_present": bool(packet_report),
            "packet_rows": packet_rows,
            "packet_rows_from_jsonl": len(packet_jsonl),
            "validation_report": validation_path,
            "validation_report_present": bool(validation),
            "validation_status": status,
            "status_jsonl": status_jsonl_path,
            "status_rows_from_jsonl": len(status_jsonl),
            "completion_ready_rows": 0,
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "errors": errors,
        })
    return rows


def expected_report(created_at: str, rows: list[dict[str, Any]], output: Path, markdown: Path, jsonl: Path) -> dict[str, Any]:
    validation_counts: dict[str, int] = {}
    for row in rows:
        validation_counts[row["validation_status"]] = validation_counts.get(row["validation_status"], 0) + 1
    return {
        "created_at": created_at,
        "local_only": True,
        "status": "blocked",
        "outputs": {"jsonl": relative(jsonl), "report": relative(output), "markdown": relative(markdown)},
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


def expected_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
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
        lines.append(f"| {row['gate_name']} | {row['packet_rows']} | {row['validation_status']} | {len(row['errors'])} |")
    lines.extend(["", "## Fail-Closed Boundary", "", "A validated packet means the operator work package is internally consistent. It is not an approval, a reviewed decision, a training label, a runtime receipt, or a release gate.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate hard-gate operator packet status board")
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN)
    parser.add_argument("--jsonl", type=Path, default=JSONL)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    failures: list[dict[str, Any]] = []
    report = load_json(args.report, failures, "board_report")
    board_rows = load_jsonl(args.jsonl, failures, "board_jsonl")
    markdown = read_text(args.markdown, failures, "board_markdown")
    rows = expected_rows(failures, str(report.get("created_at")))
    expected = expected_report(str(report.get("created_at")), rows, args.report, args.markdown, args.jsonl)
    check(board_rows == rows, failures, "board_jsonl_matches_current_sources", board_rows, rows)
    check(report == expected, failures, "board_report_matches_current_sources", report, expected)
    md = expected_markdown(expected, rows)
    check(markdown == md, failures, "board_markdown_matches_current_sources", markdown, md)
    check(expected["validated_gates"] == 6, failures, "all_six_gates_validated", expected["validated_gates"], 6)
    check(expected["validation_pending_gates"] == 0, failures, "validation_pending_zero", expected["validation_pending_gates"], 0)
    check(expected["invalid_gates"] == 0, failures, "invalid_gates_zero", expected["invalid_gates"], 0)
    check(expected["safe_for_model_claim"] is False, failures, "safe_for_model_claim_false", expected["safe_for_model_claim"], False)
    check(expected["release_ready"] is False, failures, "release_ready_false", expected["release_ready"], False)
    validation = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "success": not failures,
        "gate_rows": expected.get("gate_rows"),
        "packet_rows": expected.get("packet_rows"),
        "validated_gates": expected.get("validated_gates"),
        "validation_pending_gates": expected.get("validation_pending_gates"),
        "invalid_gates": expected.get("invalid_gates"),
        "failure_count": len(failures),
        "failures": failures[:500],
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Validation only. Passing means status board inputs are current and fail-closed, not approved.",
        "report": relative(args.report),
        "markdown": relative(args.markdown),
        "jsonl": relative(args.jsonl),
        "output": relative(args.output),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": validation["success"],
        "gate_rows": validation["gate_rows"],
        "packet_rows": validation["packet_rows"],
        "validated_gates": validation["validated_gates"],
        "failure_count": validation["failure_count"],
        "output": str(args.output),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
