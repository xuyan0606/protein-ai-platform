#!/usr/bin/env python3
"""Build local review packets for external data and tool license clearance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DATA_REGISTRY = AI_ROOT / "config" / "external_data_source_registry.local.example.json"
TOOL_REGISTRY = AI_ROOT / "config" / "foreign_tool_registry.local.example.json"
OUT = AI_ROOT / "datasets" / "governance" / "external_license_review_packets.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "external_license_review_packet_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def data_packet(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_item_id": f"data_source:{row.get('source_name')}",
        "item_type": "external_data_source",
        "name": row.get("source_name"),
        "url": row.get("url"),
        "declared_license": row.get("license"),
        "commercial_status": row.get("commercial_use_status"),
        "redistribution_status": row.get("redistribution_status"),
        "version": row.get("version"),
        "retrieved_at": row.get("retrieved_at"),
        "required_review_fields": [
            "license text or contract reference",
            "commercial use decision",
            "redistribution decision",
            "required attribution text",
            "approved version/retrieval date",
            "allowed and forbidden use confirmation",
        ],
        "review_decision": "not_reviewed",
        "approved_for_training": False,
        "approved_for_customer_delivery": False,
        "policy": "license review packet only; no clearance is granted by this artifact",
    }


def tool_packet(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_item_id": f"foreign_tool:{row.get('tool_id')}",
        "item_type": "foreign_tool",
        "name": row.get("display_name"),
        "url": row.get("license_evidence_url") or (row.get("references") or [None])[0],
        "declared_license": row.get("license_type"),
        "commercial_status": row.get("commercial_status"),
        "weight_terms_url": row.get("weight_terms_url"),
        "runtime_requirements": row.get("runtime_requirements"),
        "data_requirements": row.get("data_requirements"),
        "required_review_fields": [
            "code license clearance",
            "model weight terms clearance",
            "commercial evaluation and production boundary",
            "runtime environment approval",
            "input/output data retention and redistribution boundary",
        ],
        "review_decision": "not_reviewed",
        "approved_for_local_evaluation": False,
        "approved_for_customer_delivery": False,
        "policy": "tool review packet only; no execution or license clearance is granted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build external license review packets")
    parser.add_argument("--data-registry", type=Path, default=DATA_REGISTRY)
    parser.add_argument("--tool-registry", type=Path, default=TOOL_REGISTRY)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    data_sources = load_json(args.data_registry).get("sources", [])
    tools = load_json(args.tool_registry).get("tools", [])
    rows = [data_packet(row) for row in data_sources] + [tool_packet(row) for row in tools]
    write_jsonl(args.output, rows)
    report = {
        "local_only": True,
        "packet_rows": len(rows),
        "data_source_rows": len(data_sources),
        "foreign_tool_rows": len(tools),
        "approved_for_training_rows": 0,
        "approved_for_customer_delivery_rows": 0,
        "packet_file": str(args.output),
        "ready": False,
        "policy": "Review packets make license work explicit, but all rows remain not_reviewed until a human/legal decision is recorded elsewhere.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"packet_rows": len(rows), "ready": False, "output": str(args.report)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
