#!/usr/bin/env python3
"""Build a prioritized human-verification dispatch from the non-authoritative pre-audit."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "reports" / "sci_machine_extraction_pre_audit_20260902.jsonl"
DEFAULT_OUTPUT = ROOT / "reports" / "sci_pre_audit_human_dispatch_20260902.json"
EVIDENCE_FILES = (
    ROOT / "reports" / "sci_open_table_evidence_packets_20260902.jsonl",
    ROOT / "reports" / "sci_targeted_table_evidence_packets_20260902.jsonl",
)


def build_dispatch(rows: list[dict], evidence: dict[tuple[str, str], dict] | None = None) -> dict:
    evidence = evidence or {}
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (row.get("pre_audit_status", "needs_human_verification"), row.get("pmcid", ""), row.get("table_locator", ""))
        groups[key].append(row)
    packets = []
    for index, ((status, pmcid, table), packet_rows) in enumerate(sorted(groups.items(), key=lambda item: (item[0][0] != "precheck_candidate", item[0][1], item[0][2])), 1):
        packets.append({
            "packet_id": f"sci-preaudit-{index:02d}",
            "priority": "high" if status == "precheck_candidate" else "normal",
            "pre_audit_status": status,
            "pmcid": pmcid,
            "table_locator": table,
            "row_count": len(packet_rows),
            "rows": packet_rows,
            "source_evidence": evidence.get((pmcid, table), {"available": False}),
            "status": "ready_for_human_verification",
            "formal_decision": None,
            "training_import_allowed": False,
        })
    return {
        "packet_count": len(packets),
        "row_count": len(rows),
        "status_counts": dict(Counter(row.get("pre_audit_status", "") for row in rows)),
        "packets": packets,
        "human_verification_required": True,
        "formal_intake_authorized": False,
        "training_import_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    evidence = {}
    for path in [*EVIDENCE_FILES, *args.evidence]:
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    item = json.loads(line)
                    evidence[(item.get("pmcid", ""), item.get("table_locator", ""))] = {
                        "available": bool(item.get("raw_text")),
                        "raw_text": item.get("raw_text", ""),
                        "status": item.get("status", ""),
                    }
    report = build_dispatch(rows, evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("packet_count", "row_count", "status_counts", "training_import_allowed")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
