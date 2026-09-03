#!/usr/bin/env python3
"""Build fail-closed hard-gate formal decision review drafts for Stage 25."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_PACKETS = AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_packets.jsonl"
SUBSTRATE_PACKETS = AI_ROOT / "datasets" / "curation" / "substrate_identity_review_packets.jsonl"
STRICT_OUT = AI_ROOT / "datasets" / "curation" / "kwb_venus15b_strict_holdout_review_decisions.stage25_draft_20260806.jsonl"
SUBSTRATE_OUT = AI_ROOT / "datasets" / "curation" / "substrate_identity_review_decisions.stage25_draft_20260806.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    strict_packets = load_jsonl(STRICT_PACKETS)
    substrate_packets = load_jsonl(SUBSTRATE_PACKETS)

    strict_rows = []
    for packet in strict_packets:
        strict_rows.append({
            "review_key": packet.get("review_key"),
            "decision": "needs_more_info",
            "source_evidence_confirmed": False,
            "numbering_confirmed": False,
            "wetlab_result_confirmed": False,
            "leakage_check_passed": False,
            "approved_label": None,
            "acceptance_receipt": None,
            "review_basis": "",
            "reviewer": "",
            "reviewed_at": "",
            "notes": "",
            "review_draft": True,
            "draft_policy": "Stage 25 draft only; do not copy to formal decision file without human review and acceptance receipt.",
            "packet_id": packet.get("packet_id"),
            "formal_decision_file": "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl",
            "safe_for_model_claim": False,
            "release_ready": False,
        })

    substrate_rows = []
    for packet in substrate_packets:
        substrate_rows.append({
            "review_key": packet.get("review_key"),
            "decision": "needs_more_info",
            "identity_confirmed": False,
            "representation_type": None,
            "scope_confirmed": False,
            "condition_confirmed": False,
            "protocol_version_confirmed": False,
            "substrate_smiles": None,
            "acceptance_receipt": None,
            "review_basis": "",
            "reviewer": "",
            "reviewed_at": "",
            "notes": "",
            "review_draft": True,
            "draft_policy": "Stage 25 draft only; do not copy to formal decision file without human review and acceptance receipt. Do not infer SMILES.",
            "packet_id": packet.get("packet_id"),
            "formal_decision_file": "datasets/curation/substrate_identity_review_decisions.jsonl",
            "safe_for_model_claim": False,
            "release_ready": False,
        })

    write_jsonl(STRICT_OUT, strict_rows)
    write_jsonl(SUBSTRATE_OUT, substrate_rows)
    print(json.dumps({
        "strict_output": str(STRICT_OUT),
        "substrate_output": str(SUBSTRATE_OUT),
        "strict_draft_rows": len(strict_rows),
        "substrate_draft_rows": len(substrate_rows),
        "formal_decision_rows_written": 0,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
