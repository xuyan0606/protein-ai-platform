#!/usr/bin/env python3
"""Build fail-closed source/runtime manifest for human target and antibody lanes."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "human_target_source_runtime_manifest.json"
RECEIPTS = AI_ROOT / "datasets" / "governance" / "human_target_source_runtime_receipts.jsonl"

SOURCES: list[dict[str, Any]] = [
    {
        "source_id": "hpa_expression",
        "lane": "human_target_intelligence",
        "display_name": "Human Protein Atlas expression/subcellular source",
        "required_artifacts": ["source manifest", "version", "normal tissue/cell type units", "license scope"],
    },
    {
        "source_id": "gtex_expression",
        "lane": "human_target_intelligence",
        "display_name": "GTEx expression source",
        "required_artifacts": ["source manifest", "version", "tissue units", "RNA/protein separation policy"],
    },
    {
        "source_id": "reactome_pathway",
        "lane": "human_target_intelligence",
        "display_name": "Reactome pathway relation source",
        "required_artifacts": ["source manifest", "version", "pathway ID", "role/evidence type"],
    },
    {
        "source_id": "ligand_receptor_graph",
        "lane": "human_target_intelligence",
        "display_name": "Ligand-receptor evidence graph",
        "required_artifacts": ["edge source", "evidence type", "affinity/assay condition when claimed", "version"],
    },
    {
        "source_id": "anarci_imgt_runtime",
        "lane": "antibody_humanization",
        "display_name": "ANARCI/IMGT numbering runtime",
        "executables": ["ANARCI", "anarci"],
        "required_artifacts": ["runtime receipt", "numbering scheme", "VH/VL chain mapping", "failure log"],
    },
    {
        "source_id": "human_germline_db",
        "lane": "antibody_humanization",
        "display_name": "Human germline V/J database",
        "required_artifacts": ["database manifest", "species", "V/J gene set", "version/checksum"],
    },
    {
        "source_id": "sabdab_oas_reference",
        "lane": "antibody_humanization",
        "display_name": "SAbDab/OAS antibody reference context",
        "required_artifacts": ["source manifest", "license scope", "sequence/structure scope", "version/checksum"],
    },
]


def executable_signal(names: list[str] | None) -> dict[str, Any]:
    if not names:
        return {"required": False, "present": False, "present_names": [], "resolved_paths": {}}
    found = {name: shutil.which(name) for name in names}
    present = {name: path for name, path in found.items() if path}
    return {
        "required": True,
        "present": bool(present),
        "present_names": sorted(present),
        "resolved_paths": present,
    }


def build(
    created_at: str | None = None,
    source_created_at: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for source in SOURCES:
        signal = executable_signal(source.get("executables"))
        status = "blocked"
        blocked_reason = "source_manifest_or_runtime_receipt_missing"
        if signal["required"] and not signal["present"]:
            blocked_reason = "required_runtime_executable_missing"
        row_created_at = (source_created_at or {}).get(source["source_id"]) or datetime.now(timezone.utc).isoformat()
        row = {
            **source,
            "status": status,
            "blocked_reason": blocked_reason,
            "runtime_signal": signal,
            "source_ready": False,
            "claim_eligible": False,
            "customer_ready": False,
            "release_ready": False,
            "created_at": row_created_at,
        }
        rows.append(row)
        receipts.append({
            "receipt_id": f"{source['source_id']}-receipt",
            "source_id": source["source_id"],
            "lane": source["lane"],
            "status": status,
            "blocked_reason": blocked_reason,
            "runtime_signal": signal,
            "required_artifacts": source["required_artifacts"],
            "receipt_policy": "Local-only blocked receipt. It records missing source/runtime evidence and never asserts retrieval, numbering, target intelligence, humanization, model claim, or release readiness.",
            "created_at": row["created_at"],
        })
    report = {
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "summary": {
            "total_sources": len(rows),
            "ready_sources": 0,
            "blocked_sources": len(rows),
            "human_target_blocked_sources": sum(1 for row in rows if row["lane"] == "human_target_intelligence"),
            "antibody_blocked_sources": sum(1 for row in rows if row["lane"] == "antibody_humanization"),
        },
        "sources": rows,
        "safe_for_model_claim": False,
        "customer_ready": False,
        "release_ready": False,
        "policy": "Source/runtime manifest only. Missing source manifests and runtime receipts keep human target and antibody lanes blocked.",
    }
    return report, receipts


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human target source/runtime manifest")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    args = parser.parse_args()
    report, receipts = build()
    write_json(args.output, report)
    write_jsonl(args.receipts, receipts)
    print(json.dumps({"success": True, "sources": report["summary"]["total_sources"], "ready": 0, "blocked": report["summary"]["blocked_sources"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
