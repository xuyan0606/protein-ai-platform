#!/usr/bin/env python3
"""Build local-only blocked/ready evidence packets for tool lanes.

This script does not run ProteinMPNN, RFdiffusion, AlphaFold/ColabFold,
Vina, PDBQT, ligand topology, or GROMACS. It only records local signals:
tool contract metadata, importability, and executable presence.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_ROOT.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.tools.tool_capability_audit import tool_capability_audit  # noqa: E402


DEFAULT_REPORT = SCRIPT_ROOT / "reports" / "tool_lane_evidence_pack.json"
DEFAULT_RECEIPTS = SCRIPT_ROOT / "datasets" / "governance" / "tool_lane_evidence_receipts.jsonl"

LANES = [
    {
        "lane_id": "proteinmpnn_design",
        "tool_name": "proteinmpnn_design",
        "display_name": "ProteinMPNN",
        "runtime_kind": "proxy",
        "local_checks": ["backend import", "capability contract", "official checkpoint artifact"],
    },
    {
        "lane_id": "rfdiffusion_design",
        "tool_name": "rfdiffusion_design",
        "display_name": "RFdiffusion",
        "runtime_kind": "proxy",
        "local_checks": ["backend import", "capability contract", "official inference config"],
    },
    {
        "lane_id": "alphafold2_folding",
        "tool_name": "alphafold2_folding",
        "display_name": "AlphaFold2",
        "runtime_kind": "proxy",
        "local_checks": ["backend import", "capability contract", "official checkpoint/log artifacts"],
    },
    {
        "lane_id": "alphafold_colabfold_proxy",
        "tool_name": "alphafold_folding",
        "display_name": "AlphaFold/ColabFold proxy lane",
        "runtime_kind": "external_service_or_proxy",
        "local_checks": ["backend import", "capability contract", "service/version provenance"],
    },
    {
        "lane_id": "vina_prepare_pdbqt",
        "tool_name": "ligand_preprocess",
        "stage": "prepare_pdbqt",
        "display_name": "PDBQT preparation",
        "runtime_kind": "local_binary_gated",
        "executables": ["obabel"],
        "local_checks": ["OpenBabel executable", "PDBQT stage contract"],
    },
    {
        "lane_id": "vina_docking",
        "tool_name": "ligand_preprocess",
        "stage": "vina_docking",
        "display_name": "Vina docking",
        "runtime_kind": "local_binary_gated",
        "executables": ["vina"],
        "local_checks": ["Vina executable", "pose log", "pose artifact"],
    },
    {
        "lane_id": "ligand_topology",
        "tool_name": "ligand_preprocess",
        "stage": "ligand_topology",
        "display_name": "Ligand topology",
        "runtime_kind": "local_binary_gated",
        "executables": ["acpype"],
        "local_checks": ["ACPYPE/AmberTools executable", "topology artifacts"],
    },
    {
        "lane_id": "gromacs_long_md",
        "tool_name": "gromacs_md",
        "display_name": "GROMACS long task",
        "runtime_kind": "local_binary_gated",
        "executables": ["gmx", "gmx_mpi"],
        "local_checks": ["GROMACS executable", "TPR/XTC/TRR/EDR/XVG artifacts", "task receipt"],
    },
]


def load_contracts() -> dict[str, dict[str, Any]]:
    audit = tool_capability_audit([row["tool_name"] for row in LANES])
    return {row["tool"]: row for row in audit.get("capabilities", []) if isinstance(row, dict)}


def local_binary_status(names: list[str]) -> dict[str, Any]:
    found = {name: shutil.which(name) for name in names}
    present = [name for name, path in found.items() if path]
    return {
        "present": bool(present),
        "present_names": present,
        "resolved_paths": {name: path for name, path in found.items() if path},
    }


def lane_status(lane: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    runtime_kind = lane["runtime_kind"]
    executables = lane.get("executables") or []
    binary_status = local_binary_status(executables) if executables else {"present": False, "present_names": [], "resolved_paths": {}}
    capability_status = contract.get("capability_status", "unknown")

    if runtime_kind == "proxy":
        status = "blocked"
        reason = "proxy_only_no_official_runtime_artifact"
    elif runtime_kind == "external_service_or_proxy":
        status = "blocked"
        reason = "external_service_provenance_not_attached"
    elif runtime_kind == "local_binary_gated":
        if binary_status["present"]:
            status = "ready"
            reason = "local_binary_detected"
        else:
            status = "blocked"
            reason = "required_local_binary_missing"
    else:
        status = "blocked"
        reason = "unknown_runtime_kind"

    if capability_status == "real_runtime_gated" and status == "ready":
        evidence_state = "ready_to_verify"
    elif capability_status in {"proxy", "runtime_unverified", "proxy_or_external_lookup"}:
        evidence_state = "blocked_proxy"
    else:
        evidence_state = "blocked_runtime_missing" if status == "blocked" else "ready_to_verify"

    return {
        "lane_id": lane["lane_id"],
        "tool_name": lane["tool_name"],
        "stage": lane.get("stage"),
        "display_name": lane["display_name"],
        "runtime_kind": runtime_kind,
        "capability_status": capability_status,
        "status": status,
        "evidence_state": evidence_state,
        "blocked_reason": reason if status == "blocked" else None,
        "ready_reason": reason if status == "ready" else None,
        "local_binary": binary_status,
        "local_checks": lane.get("local_checks", []),
        "contract_boundary": contract.get("boundary"),
        "minimum_artifacts": contract.get("minimum_artifacts") or [],
        "report_action": contract.get("report_action"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_pack() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    contracts = load_contracts()
    lanes: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for lane in LANES:
        contract = contracts.get(lane["tool_name"], {})
        row = lane_status(lane, contract)
        lanes.append(row)
        receipts.append({
            "receipt_id": f"{row['lane_id']}-receipt",
            "lane_id": row["lane_id"],
            "tool_name": row["tool_name"],
            "stage": row["stage"],
            "status": row["status"],
            "evidence_state": row["evidence_state"],
            "blocked_reason": row["blocked_reason"],
            "ready_reason": row["ready_reason"],
            "local_binary": row["local_binary"],
            "contract_capability_status": row["capability_status"],
            "contract_boundary": row["contract_boundary"],
            "minimum_artifacts": row["minimum_artifacts"],
            "local_checks": row["local_checks"],
            "receipt_policy": "Local-only receipt. It records file/runtime signals and never asserts actual model inference or docking completion.",
            "created_at": row["generated_at"],
        })

    summary = {
        "total_lanes": len(lanes),
        "ready_lanes": sum(1 for row in lanes if row["status"] == "ready"),
        "blocked_lanes": sum(1 for row in lanes if row["status"] == "blocked"),
        "proxy_lanes": sum(1 for row in lanes if row["capability_status"] in {"proxy", "runtime_unverified", "proxy_or_external_lookup"}),
        "real_runtime_gated_lanes": sum(1 for row in lanes if row["capability_status"] == "real_runtime_gated"),
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "summary": summary,
        "lanes": lanes,
        "policy": "This evidence pack is local-signal only. A ready lane means the local binary or contract signal is visible; it does not mean the model runtime executed.",
    }
    return report, receipts


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local-only evidence pack for tool lanes")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    args = parser.parse_args()

    report, receipts = build_pack()
    write_json(args.output, report)
    write_jsonl(args.receipts, receipts)
    print(json.dumps({
        "success": True,
        "lanes": report["summary"]["total_lanes"],
        "ready": report["summary"]["ready_lanes"],
        "blocked": report["summary"]["blocked_lanes"],
        "output": str(args.output),
        "receipts": str(args.receipts),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
