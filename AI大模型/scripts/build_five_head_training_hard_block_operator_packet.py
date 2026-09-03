#!/usr/bin/env python3
"""Build the fail-closed operator packet for remaining five-head training blockers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "five_head_training_hard_block_operator_packet.json"
EXPECTED_HEADS = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_packet(base: Path = AI_ROOT) -> dict[str, Any]:
    status = load_json(base / "reports" / "model_status.json")
    unlock = load_json(base / "reports" / "wet_lab_mutant_library_unlock_status_report.json")
    worklist = load_json(base / "reports" / "wet_lab_mutant_library_feedback_authorization_worklist_report.json")
    numbering = load_json(base / "reports" / "numbering_review_operator_queue.json")
    heads_source = status.get("heads") if isinstance(status.get("heads"), dict) else {}
    heads = {}
    for name in EXPECTED_HEADS:
        row = heads_source.get(name) if isinstance(heads_source.get(name), dict) else {}
        label_rows = as_int(row.get("label_rows"))
        minimum_rows = as_int(row.get("minimum_rows")) or 100
        heads[name] = {
            "label_rows": label_rows,
            "minimum_rows": minimum_rows,
            "missing_to_minimum": max(minimum_rows - label_rows, 0),
            "ready": row.get("ready") is True,
            "minimum_replicates": 3,
            "minimum_groups": 10,
        }
    required = [
        "reviewed_16b_parent_sequence",
        "reviewed_4g_parent_sequence",
        "explicit_replicate_metadata_for_activity_and_stability_rows",
        "authorize_or_reject_e331q_critical_tradeoff_metrics",
        "reviewed_numbering_decisions_for_claim_eligible_labels",
        "plate_or_well_assay_success_labels",
        "substrate_identity_and_condition_labels",
    ]
    packet = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked_waiting_for_human_or_external_input",
        "training_execution_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "ready_head_count": sum(1 for row in heads.values() if row["ready"]),
        "heads": heads,
        "wet_lab": {
            "hard_blockers": list(unlock.get("hard_blockers") or []),
            "authorized_rows": as_int((unlock.get("wet_lab_summary") or {}).get("authorized_rows")),
            "numeric_training_candidate_rows": as_int(
                (unlock.get("wet_lab_summary") or {}).get("numeric_training_candidate_rows")
            ),
            "blocked_waiting_for_authorization_rows": as_int(worklist.get("blocked_waiting_for_authorization_rows")),
            "critical_tradeoff_feedback_candidate_ids": list(
                worklist.get("critical_tradeoff_feedback_candidate_ids") or []
            ),
        },
        "numbering": {
            "open_rows": as_int(numbering.get("open_numbering_rows")),
            "decision_rows": as_int(numbering.get("decision_rows")),
        },
        "required_human_inputs": required,
        "operator_files": [
            "datasets/feedback/wet_lab_mutant_library_project_sequences.local.jsonl",
            "datasets/feedback/wet_lab_mutant_library_sequence_request_packets.jsonl",
            "datasets/feedback/wet_lab_mutant_library_feedback_authorizations.jsonl",
            "datasets/feedback/wet_lab_mutant_library_feedback_authorization_worklist.jsonl",
            "datasets/curation/numbering_curation_decisions.jsonl",
            "reports/numbering_review_operator_queue.json",
        ],
        "cannot_auto_complete": [
            "Do not invent 16B/4G parent sequences; existing Venus-15B and session sequences fail WT-residue checks.",
            "Do not auto-authorize E331Q tradeoff metrics.",
            "Do not promote ProThermDB/generated numbering rows into claim-eligible labels.",
            "Do not treat research smoke or feature rows as formal training completion.",
        ],
        "policy": (
            "This packet only lists remaining human/external inputs. It never writes labels, "
            "approves numbering, or opens training/model/release gates."
        ),
    }
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Build five-head training hard-block operator packet")
    parser.add_argument("--base", type=Path, default=AI_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    packet = build_packet(args.base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": packet["status"],
                "ready_head_count": packet["ready_head_count"],
                "required_human_inputs": len(packet["required_human_inputs"]),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
