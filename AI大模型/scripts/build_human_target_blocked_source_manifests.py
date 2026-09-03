#!/usr/bin/env python3
"""Build lightly split blocked manifests for human target source/runtime lanes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "reports" / "human_target_source_runtime_manifest.json"
OUT = AI_ROOT / "reports" / "human_target_blocked_source_manifest_index.json"
SPLIT_DIR = AI_ROOT / "reports" / "human_target_sources"

SPLITS = {
    "hpa_expression": "human_target_sources/hpa_expression_source_manifest.json",
    "gtex_expression": "human_target_sources/gtex_expression_source_manifest.json",
    "reactome_pathway": "human_target_sources/reactome_pathway_source_manifest.json",
    "ligand_receptor_graph": "human_target_sources/ligand_receptor_graph_source_manifest.json",
    "anarci_imgt_runtime": "human_target_sources/anarci_imgt_runtime_manifest.json",
    "human_germline_db": "human_target_sources/human_germline_db_source_manifest.json",
    "sabdab_oas_reference": "human_target_sources/sabdab_oas_reference_source_manifest.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_manifests(
    input_path: Path = INPUT,
    created_at: str | None = None,
    split_created_at: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = load_json(input_path)
    sources = payload.get("sources") or []
    by_id = {row.get("source_id"): row for row in sources if isinstance(row, dict)}
    split_payloads: dict[str, dict[str, Any]] = {}

    index: dict[str, Any] = {
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "source_manifest_index": [],
        "blocked_sources": len(sources),
        "ready_sources": 0,
        "policy": "Split manifests are still blocked and only isolate each source/runtime receipt for separate audit.",
    }

    for source_id, rel_path in SPLITS.items():
        row = by_id.get(source_id)
        if not row:
            continue
        split_payload = {
            "created_at": (split_created_at or {}).get(source_id) or datetime.now(timezone.utc).isoformat(),
            "local_only": True,
            "source_id": source_id,
            "lane": row.get("lane"),
            "display_name": row.get("display_name"),
            "status": row.get("status"),
            "blocked_reason": row.get("blocked_reason"),
            "runtime_signal": row.get("runtime_signal"),
            "required_artifacts": row.get("required_artifacts"),
            "source_ready": False,
            "claim_eligible": False,
            "customer_ready": False,
            "release_ready": False,
            "policy": "Split source/runtime manifest only. This is still blocked and does not imply data availability.",
        }
        split_payloads[source_id] = split_payload
        index["source_manifest_index"].append(
            {
                "source_id": source_id,
                "path": rel_path,
                "status": "blocked",
                "blocked_reason": row.get("blocked_reason"),
            }
        )
    return index, split_payloads


def main() -> int:
    parser = argparse.ArgumentParser(description="Build blocked human target source manifests")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    args = parser.parse_args()

    split_dir = args.split_dir
    split_dir.mkdir(parents=True, exist_ok=True)
    index, split_payloads = build_manifests(args.input)

    for source_id, split_payload in split_payloads.items():
        rel_path = SPLITS[source_id]
        write_json(args.split_dir / Path(rel_path).name, split_payload)

    write_json(args.output, index)
    print(json.dumps({"success": True, "sources": len(index["source_manifest_index"]), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
