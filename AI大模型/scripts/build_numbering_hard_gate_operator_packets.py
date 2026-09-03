#!/usr/bin/env python3
"""Build fail-closed operator packets for the reviewed numbering hard gate.

The output is an operator scaffold only. It groups the open numbering queue
into existing small review packets and puts semantic conflicts first. It never
modifies reviewed decisions, applies curation, imports labels, or runs a
pipeline/manifest step.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OPERATOR_QUEUE = AI_ROOT / "reports" / "numbering_review_operator_queue.json"
SEMANTIC_CONFLICT_REPORT = AI_ROOT / "reports" / "numbering_decision_semantic_conflict_report.json"
PROVENANCE_REPORT = AI_ROOT / "reports" / "label_provenance_audit_report.json"
SEMANTIC_CONFLICT_QUEUE = (
    AI_ROOT / "datasets" / "curation" / "numbering_decision_semantic_conflict_queue.jsonl"
)
REVIEW_WORKLIST = AI_ROOT / "datasets" / "curation" / "numbering_review_worklist.jsonl"
PACKETS_OUT = AI_ROOT / "datasets" / "governance" / "numbering_hard_gate_operator_packets.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "numbering_hard_gate_operator_packet_report.json"
MARKDOWN_OUT = AI_ROOT / "reports" / "numbering_hard_gate_operator_packets.md"

POLICY = (
    "Fail-closed reviewed-numbering operator packets only. These packets guide human review; "
    "they do not write numbering_curation_decisions.jsonl, apply curation, import labels, "
    "run a safe pipeline, update a manifest, enable training, support model claims, or grant release readiness."
)

FORBIDDEN_OUTPUTS = [
    "datasets/curation/numbering_curation_decisions.jsonl",
    "datasets/curated/enzyme_mutation_supervised_claim_eligible.jsonl",
    "reports/data_lake_manifest.json",
    "reports/local_release_manifest.json",
    "safe training pipeline outputs",
]

PREVIEW_FIELDS = (
    "record_id",
    "priority",
    "review_rank",
    "review_bucket",
    "uniprot_id",
    "mutation",
    "reported_position",
    "reported_wild_type",
    "reported_mutant",
    "current_sequence_residue",
    "literature_ref",
    "audit_recommended_decision",
    "source_lineage_group",
    "operator_next_action",
)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path, input_errors: list[str], required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            input_errors.append(f"missing_input:{relative(path)}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        input_errors.append(f"invalid_json:{relative(path)}")
        return {}
    if not isinstance(value, dict):
        input_errors.append(f"invalid_json_object:{relative(path)}")
        return {}
    return value


def load_jsonl(path: Path, input_errors: list[str], required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            input_errors.append(f"missing_input:{relative(path)}")
        return []

    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        input_errors.append(f"invalid_jsonl:{relative(path)}")
        return []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            input_errors.append(f"invalid_jsonl:{relative(path)}:{line_number}")
            continue
        if not isinstance(value, dict):
            input_errors.append(f"invalid_jsonl_object:{relative(path)}:{line_number}")
            continue
        rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def selected_row(row: dict[str, Any], fields: tuple[str, ...] = PREVIEW_FIELDS) -> dict[str, Any]:
    return {field: row.get(field) for field in fields}


def index_unique(
    rows: list[dict[str, Any]],
    key_name: str,
    input_errors: list[str],
    source_name: str,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_name) or "")
        if not key:
            input_errors.append(f"missing_{source_name}_{key_name}")
            continue
        if key in indexed:
            input_errors.append(f"duplicate_{source_name}:{key}")
            continue
        indexed[key] = row
    return indexed


def build_conflict_packets(
    conflict_rows: list[dict[str, Any]],
    queue_by_record: dict[str, dict[str, Any]],
    provenance_gate: dict[str, Any],
    input_errors: list[str],
) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for index, conflict in enumerate(conflict_rows, start=1):
        record_id = str(conflict.get("record_id") or "")
        queue_row = queue_by_record.get(record_id, {})
        if not queue_row:
            input_errors.append(f"semantic_conflict_missing_operator_queue_row:{record_id}")
        conflict_id = str(conflict.get("conflict_id") or f"numbering_semantic_conflict:{index:04d}")
        source_refs = conflict.get("source_refs")
        if not isinstance(source_refs, list):
            source_refs = []
        allowed_actions = conflict.get("allowed_resolution_actions")
        if not isinstance(allowed_actions, list):
            allowed_actions = []
        packet = {
            "packet_id": f"numbering-hard-gate-semantic-conflict-{index:04d}",
            "execution_order": index,
            "packet_type": "semantic_conflict",
            "workstream": "reviewed_numbering_hard_gate",
            "priority": "P0",
            "status": "open_blocked",
            "record_count": 1,
            "record_ids": [record_id] if record_id else [],
            "conflict_id": conflict_id,
            "conflict_type": conflict.get("conflict_type"),
            "uniprot_id": conflict.get("uniprot_id") or queue_row.get("uniprot_id"),
            "mutation": conflict.get("mutation") or queue_row.get("mutation"),
            "current_decision": conflict.get("current_decision"),
            "human_note_interpretation": conflict.get("human_note_interpretation"),
            "deep_audit_recommended_decision": conflict.get("deep_audit_recommended_decision"),
            "recommended_resolution": conflict.get("recommended_resolution"),
            "allowed_resolution_actions": allowed_actions,
            "source_refs": source_refs,
            "deep_audit_flags": conflict.get("deep_audit_flags") or [],
            "operator_next_action": (
                "Resolve the notes/decision conflict explicitly; do not infer or rewrite the decision from this packet."
            ),
            "row_preview": [selected_row(queue_row)] if queue_row else [],
            "label_provenance_gate": provenance_gate,
            "completion_ready": False,
            "requires_human_input": True,
            "decision_written_by_packet": False,
            "curation_apply_by_packet": False,
            "label_import_by_packet": False,
            "safe_pipeline_integration_allowed": False,
            "manifest_update_allowed": False,
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": POLICY,
        }
        packets.append(packet)
    return packets


def build_open_packets(
    open_rows: list[dict[str, Any]],
    provenance_gate: dict[str, Any],
    start_order: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in open_rows:
        packet_key = str(row.get("packet_id") or row.get("review_bucket") or "unassigned")
        grouped[packet_key].append(row)

    packets: list[dict[str, Any]] = []
    for offset, (packet_key, rows) in enumerate(grouped.items(), start=0):
        rows = sorted(
            rows,
            key=lambda row: (
                int(row.get("operator_order") or 999999),
                int(row.get("review_rank") or 999999),
                str(row.get("record_id") or ""),
            ),
        )
        bucket_counts = Counter(str(row.get("review_bucket") or "unassigned") for row in rows)
        priority_counts = Counter(str(row.get("priority") or "unassigned") for row in rows)
        review_ranks = [
            int(row["review_rank"])
            for row in rows
            if isinstance(row.get("review_rank"), int) or str(row.get("review_rank") or "").isdigit()
        ]
        record_ids = [str(row.get("record_id") or "") for row in rows if row.get("record_id")]
        packet = {
            "packet_id": f"numbering-hard-gate-open-{packet_key}",
            "execution_order": start_order + offset,
            "packet_type": "open_numbering_batch",
            "workstream": "reviewed_numbering_hard_gate",
            "priority": min(priority_counts) if priority_counts else "P0",
            "status": "open_blocked",
            "source_packet_id": packet_key,
            "review_bucket": next(iter(bucket_counts), "unassigned"),
            "record_count": len(rows),
            "record_ids": record_ids,
            "bucket_counts": dict(sorted(bucket_counts.items())),
            "priority_counts": dict(sorted(priority_counts.items())),
            "review_rank_range": [min(review_ranks), max(review_ranks)] if review_ranks else [],
            "row_preview": [selected_row(row) for row in rows[:3]],
            "operator_next_action": (
                "Review each referenced row against original source, numbering system, WT/mutant residues, "
                "and a source receipt; create a separate explicit reviewed decision only after evidence is sufficient."
            ),
            "required_review_checks": [
                "confirm original source really reports this protein and mutation",
                "confirm numbering system and isoform/canonical sequence version",
                "confirm wild-type residue and mutant residue against source evidence",
                "confirm raw-source checksum or reviewed source receipt before any claim-eligible use",
            ],
            "label_provenance_gate": provenance_gate,
            "completion_ready": False,
            "requires_human_input": True,
            "decision_written_by_packet": False,
            "curation_apply_by_packet": False,
            "label_import_by_packet": False,
            "safe_pipeline_integration_allowed": False,
            "manifest_update_allowed": False,
            "training_unlocked": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": POLICY,
        }
        packets.append(packet)
    return packets


def markdown(report: dict[str, Any], packets: list[dict[str, Any]]) -> str:
    summary = report["summary"]
    lines = [
        "# Numbering Hard-Gate Operator Packets",
        "",
        f"Generated: {report['created_at']}",
        "",
        "Operator navigation only. These packets are not reviewed decisions and are not supervised labels.",
        "",
        "## Status",
        "",
        f"- Status: `{report['status']}`",
        f"- Packet rows: `{summary['packet_rows']}`",
        f"- Semantic conflict packets: `{summary['semantic_conflict_packet_rows']}`",
        f"- Open numbering packets: `{summary['open_numbering_packet_rows']}`",
        f"- Semantic conflict rows: `{summary['semantic_conflict_rows']}`",
        f"- Open numbering rows: `{summary['open_numbering_rows']}`",
        f"- Largest open packet: `{summary['largest_open_packet_rows']}` rows",
        f"- Label provenance hard gate: `{report['label_provenance_gate']['hard_gate_status']}`",
        f"- Claim-eligible labels: `{report['label_provenance_gate']['claim_eligible_rows']}`",
        f"- Safe for model claim: `{str(report['safe_for_model_claim']).lower()}`",
        f"- Training unlocked: `{str(report['training_unlocked']).lower()}`",
        "",
        "## Semantic Conflicts First",
        "",
        "| order | packet | conflict | record | UniProt | mutation | current decision | recommended resolution |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for packet in packets:
        if packet["packet_type"] != "semantic_conflict":
            continue
        lines.append(
            "| {execution_order} | {packet_id} | {conflict_id} | {record_id} | {uniprot_id} | {mutation} | "
            "{current_decision} | {recommended_resolution} |".format(
                execution_order=packet["execution_order"],
                packet_id=packet["packet_id"],
                conflict_id=packet.get("conflict_id"),
                record_id=(packet.get("record_ids") or [""])[0],
                uniprot_id=packet.get("uniprot_id"),
                mutation=packet.get("mutation"),
                current_decision=packet.get("current_decision"),
                recommended_resolution=packet.get("recommended_resolution"),
            )
        )
    lines.extend(
        [
            "",
            "## Open Numbering Batches",
            "",
            "| order | packet | source packet | bucket | rows | review ranks | priorities |",
            "|---:|---|---|---|---:|---|---|",
        ]
    )
    for packet in packets:
        if packet["packet_type"] != "open_numbering_batch":
            continue
        lines.append(
            "| {execution_order} | {packet_id} | {source_packet_id} | {review_bucket} | {record_count} | "
            "{review_rank_range} | {priority_counts} |".format(
                execution_order=packet["execution_order"],
                packet_id=packet["packet_id"],
                source_packet_id=packet.get("source_packet_id"),
                review_bucket=packet.get("review_bucket"),
                record_count=packet.get("record_count"),
                review_rank_range=packet.get("review_rank_range"),
                priority_counts=packet.get("priority_counts"),
            )
        )
    lines.extend(
        [
            "",
            "## Fail-Closed Boundary",
            "",
            report["policy"],
            "",
            "Forbidden outputs/actions:",
        ]
    )
    lines.extend(f"- `{item}`" for item in report["forbidden_outputs"])
    lines.extend(
        [
            "",
            "No packet is completion-ready. Human review must produce a separate explicit decision and "
            "separate validation/apply actions; this scaffold does not perform them.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build reviewed numbering hard-gate operator packets")
    parser.add_argument("--operator-queue", type=Path, default=OPERATOR_QUEUE)
    parser.add_argument("--semantic-conflict-report", type=Path, default=SEMANTIC_CONFLICT_REPORT)
    parser.add_argument("--provenance-report", type=Path, default=PROVENANCE_REPORT)
    parser.add_argument("--semantic-conflict-queue", type=Path, default=SEMANTIC_CONFLICT_QUEUE)
    parser.add_argument("--review-worklist", type=Path, default=REVIEW_WORKLIST)
    parser.add_argument("--output", type=Path, default=PACKETS_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--markdown", type=Path, default=MARKDOWN_OUT)
    args = parser.parse_args()

    input_errors: list[str] = []
    operator_queue = load_json(args.operator_queue, input_errors)
    semantic_report = load_json(args.semantic_conflict_report, input_errors)
    provenance_report = load_json(args.provenance_report, input_errors)
    conflict_rows = load_jsonl(args.semantic_conflict_queue, input_errors)
    worklist_rows = load_jsonl(args.review_worklist, input_errors, required=False)

    queue_rows = operator_queue.get("rows")
    if not isinstance(queue_rows, list):
        input_errors.append("operator_queue_rows_missing_or_invalid")
        queue_rows = []
    queue_rows = [row for row in queue_rows if isinstance(row, dict)]
    queue_by_record = index_unique(queue_rows, "record_id", input_errors, "operator_queue")

    conflict_by_record = index_unique(conflict_rows, "record_id", input_errors, "semantic_conflict_queue")
    queue_conflict_rows = [
        row for row in queue_rows if row.get("operator_status") == "semantic_conflict"
    ]
    queue_conflict_by_record = {str(row.get("record_id")): row for row in queue_conflict_rows}
    conflict_records = set(conflict_by_record) | set(queue_conflict_by_record)
    ordered_conflicts: list[dict[str, Any]] = []
    for record_id in sorted(
        conflict_records,
        key=lambda value: (
            int(queue_by_record.get(value, {}).get("operator_order") or 999999),
            value,
        ),
    ):
        conflict = conflict_by_record.get(record_id)
        if conflict is None:
            queue_row = queue_conflict_by_record[record_id]
            conflict = {
                "record_id": record_id,
                "uniprot_id": queue_row.get("uniprot_id"),
                "mutation": queue_row.get("mutation"),
                "current_decision": (queue_row.get("existing_decision") or {}).get("decision"),
                "human_note_interpretation": "reject_label",
                "conflict_type": "semantic_conflict_from_operator_queue",
                "recommended_resolution": "human_review_required",
                "allowed_resolution_actions": [],
                "source_refs": ((queue_row.get("existing_decision") or {}).get("source_refs") or []),
                "deep_audit_flags": queue_row.get("audit_flags") or [],
            }
            input_errors.append(f"semantic_conflict_queue_row_missing:{record_id}")
        ordered_conflicts.append(conflict)

    conflict_ids = {str(row.get("record_id") or "") for row in ordered_conflicts}
    open_rows = [
        row
        for row in queue_rows
        if row.get("operator_status") == "todo" and str(row.get("record_id") or "") not in conflict_ids
    ]
    if not queue_rows and worklist_rows:
        open_rows = [
            {**row, "operator_status": "todo", "operator_order": index}
            for index, row in enumerate(worklist_rows, start=1)
        ]
        input_errors.append("operator_queue_empty_used_review_worklist_fallback")

    expected_queue_rows = operator_queue.get("queue_rows")
    if isinstance(expected_queue_rows, int) and expected_queue_rows != len(queue_rows):
        input_errors.append(f"operator_queue_count_mismatch:{expected_queue_rows}!={len(queue_rows)}")
    expected_open_rows = operator_queue.get("open_numbering_rows")
    if isinstance(expected_open_rows, int) and expected_open_rows != len(open_rows):
        input_errors.append(f"operator_queue_open_count_mismatch:{expected_open_rows}!={len(open_rows)}")
    if worklist_rows and len(worklist_rows) != len(queue_rows):
        input_errors.append(f"review_worklist_count_mismatch:{len(worklist_rows)}!={len(queue_rows)}")
    worklist_by_record = index_unique(worklist_rows, "record_id", input_errors, "review_worklist")
    missing_worklist_rows = sorted(
        record_id for record_id in [str(row.get("record_id") or "") for row in open_rows]
        if record_id and record_id not in worklist_by_record
    )
    if worklist_rows and missing_worklist_rows:
        input_errors.append(f"review_worklist_missing_open_rows:{len(missing_worklist_rows)}")

    provenance_gate = {
        "hard_gate_status": provenance_report.get("hard_gate_status", "unknown"),
        "strict_rows": provenance_report.get("strict_rows", 0),
        "claim_eligible_rows": provenance_report.get("claim_eligible_rows", 0),
        "synthetic_or_unreceipted_rows": provenance_report.get("synthetic_or_unreceipted_rows", 0),
        "safe_for_training_pipeline": bool(provenance_report.get("safe_for_training_pipeline", False)),
        "safe_for_model_claim": False,
    }

    conflict_packets = build_conflict_packets(
        ordered_conflicts,
        queue_by_record,
        provenance_gate,
        input_errors,
    )
    open_packets = build_open_packets(
        open_rows,
        provenance_gate,
        start_order=len(conflict_packets) + 1,
    )
    packets = conflict_packets + open_packets

    open_bucket_counts = Counter(str(row.get("review_bucket") or "unassigned") for row in open_rows)
    packet_bucket_counts = Counter(str(packet.get("review_bucket") or "unassigned") for packet in open_packets)
    packet_size_values = [int(packet["record_count"]) for packet in open_packets]
    conflict_report_rows = semantic_report.get("semantic_conflict_rows")
    if isinstance(conflict_report_rows, int) and conflict_report_rows != len(ordered_conflicts):
        input_errors.append(f"semantic_conflict_report_count_mismatch:{conflict_report_rows}!={len(ordered_conflicts)}")

    created_at = datetime.now(timezone.utc).isoformat()
    report = {
        "created_at": created_at,
        "local_only": True,
        "status": "blocked",
        "inputs": {
            "numbering_review_operator_queue": relative(args.operator_queue),
            "numbering_decision_semantic_conflict_report": relative(args.semantic_conflict_report),
            "label_provenance_audit_report": relative(args.provenance_report),
            "numbering_decision_semantic_conflict_queue": relative(args.semantic_conflict_queue),
            "numbering_review_worklist": relative(args.review_worklist),
        },
        "input_presence": {
            "numbering_review_operator_queue": args.operator_queue.exists(),
            "numbering_decision_semantic_conflict_report": args.semantic_conflict_report.exists(),
            "label_provenance_audit_report": args.provenance_report.exists(),
            "numbering_decision_semantic_conflict_queue": args.semantic_conflict_queue.exists(),
            "numbering_review_worklist": args.review_worklist.exists(),
        },
        "input_errors": input_errors,
        "summary": {
            "packet_rows": len(packets),
            "semantic_conflict_packet_rows": len(conflict_packets),
            "open_numbering_packet_rows": len(open_packets),
            "semantic_conflict_rows": len(ordered_conflicts),
            "open_numbering_rows": len(open_rows),
            "open_numbering_bucket_counts": dict(sorted(open_bucket_counts.items())),
            "open_numbering_packet_counts_by_bucket": dict(sorted(packet_bucket_counts.items())),
            "largest_open_packet_rows": max(packet_size_values, default=0),
            "smallest_open_packet_rows": min(packet_size_values, default=0),
            "completion_ready_rows": 0,
            "requires_human_input_rows": len(packets),
            "decision_rows_written": 0,
            "curation_applied_rows": 0,
            "label_imported_rows": 0,
        },
        "operator_status_counts": dict(sorted(Counter(str(row.get("operator_status")) for row in queue_rows).items())),
        "semantic_conflict_report_status": {
            "reported_rows": semantic_report.get("semantic_conflict_rows", 0),
            "reported_open_rows": semantic_report.get("open_conflict_rows", 0),
            "conflict_type_counts": semantic_report.get("conflict_type_counts", {}),
        },
        "label_provenance_gate": provenance_gate,
        "packet_ids": [packet["packet_id"] for packet in packets],
        "outputs": {
            "packets": relative(args.output),
            "report": relative(args.report),
            "markdown": relative(args.markdown),
        },
        "forbidden_outputs": FORBIDDEN_OUTPUTS,
        "write_numbering_curation_decisions_allowed": False,
        "apply_curation_allowed": False,
        "label_import_allowed": False,
        "safe_pipeline_integration_allowed": False,
        "manifest_update_allowed": False,
        "training_unlocked": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": POLICY,
    }

    write_jsonl(args.output, packets)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(markdown(report, packets), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "packet_rows": report["summary"]["packet_rows"],
                "semantic_conflict_rows": report["summary"]["semantic_conflict_rows"],
                "open_numbering_rows": report["summary"]["open_numbering_rows"],
                "open_numbering_packet_rows": report["summary"]["open_numbering_packet_rows"],
                "completion_ready_rows": report["summary"]["completion_ready_rows"],
                "input_errors": len(input_errors),
                "safe_for_model_claim": report["safe_for_model_claim"],
                "outputs": report["outputs"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
