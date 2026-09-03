#!/usr/bin/env python3
"""Validate the local-only tool lane evidence pack.

The validator checks that proxy tools are not promoted to runtime-ready and
that binary-gated lanes only become ready when local executables are visible.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = SCRIPT_ROOT / "reports" / "tool_lane_evidence_pack.json"
DEFAULT_RECEIPTS = SCRIPT_ROOT / "datasets" / "governance" / "tool_lane_evidence_receipts.jsonl"
DEFAULT_OUT = SCRIPT_ROOT / "reports" / "tool_lane_evidence_pack_validation_report.json"
BUILDER = SCRIPT_ROOT / "scripts" / "build_tool_lane_evidence_pack.py"

EXPECTED_LANES = {
    "proteinmpnn_design",
    "rfdiffusion_design",
    "alphafold2_folding",
    "alphafold_colabfold_proxy",
    "vina_prepare_pdbqt",
    "vina_docking",
    "ligand_topology",
    "gromacs_long_md",
}

PROXY_LANES = {
    "proteinmpnn_design",
    "rfdiffusion_design",
    "alphafold2_folding",
    "alphafold_colabfold_proxy",
}

LOCAL_BINARY_LANES = {
    "vina_prepare_pdbqt": ["obabel"],
    "vina_docking": ["vina"],
    "ligand_topology": ["acpype"],
    "gromacs_long_md": ["gmx", "gmx_mpi"],
}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(SCRIPT_ROOT))
    except ValueError:
        return str(path)


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("build_tool_lane_evidence_pack", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load builder: {BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate tool lane evidence pack")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    builder = load_builder()
    report = load_json(args.report)
    receipts = load_jsonl(args.receipts)
    failures: list[dict[str, Any]] = []
    expected_report, expected_receipts = builder.build_pack()
    expected_report["created_at"] = report.get("created_at")
    for expected_lane, observed_lane in zip(expected_report.get("lanes") or [], report.get("lanes") or []):
        expected_lane["generated_at"] = observed_lane.get("generated_at") if isinstance(observed_lane, dict) else expected_lane.get("generated_at")
    for expected_receipt, observed_receipt in zip(expected_receipts, receipts):
        if isinstance(observed_receipt, dict):
            expected_receipt["created_at"] = observed_receipt.get("created_at")

    lanes = report.get("lanes") or []
    lane_by_id = {str(row.get("lane_id") or ""): row for row in lanes if isinstance(row, dict)}
    expected_lane_ids = {str(row.get("lane_id") or "") for row in expected_report.get("lanes") or [] if isinstance(row, dict)}
    expected_receipt_ids = {str(row.get("receipt_id") or "") for row in expected_receipts if isinstance(row, dict)}
    receipt_ids = {str(row.get("receipt_id") or "") for row in receipts if isinstance(row, dict)}
    missing = sorted(EXPECTED_LANES - set(lane_by_id))
    extra = sorted(set(lane_by_id) - EXPECTED_LANES)
    if report != expected_report:
        failures.append({"check": "report_matches_current_builder_projection", "observed": report, "expected": expected_report})
    if receipts != expected_receipts:
        failures.append({"check": "receipts_match_current_builder_projection", "observed": receipts, "expected": expected_receipts})
    if set(lane_by_id) != expected_lane_ids:
        failures.append({"check": "lane_ids_match_builder_contract", "observed": sorted(lane_by_id), "expected": sorted(expected_lane_ids)})
    if receipt_ids != expected_receipt_ids:
        failures.append({"check": "receipt_ids_match_builder_contract", "observed": sorted(receipt_ids), "expected": sorted(expected_receipt_ids)})
    if missing:
        failures.append({"check": "expected_lanes_present", "missing": missing})
    if extra:
        failures.append({"check": "no_unexpected_lanes", "extra": extra})
    if len(receipts) != len(lanes):
        failures.append({"check": "receipt_count_matches_lanes", "expected": len(lanes), "actual": len(receipts)})

    for lane_id in sorted(EXPECTED_LANES):
        lane = lane_by_id.get(lane_id)
        if not lane:
            continue
        status = lane.get("status")
        capability_status = lane.get("capability_status")
        if lane_id in PROXY_LANES and status != "blocked":
            failures.append({"check": "proxy_lane_must_remain_blocked", "lane_id": lane_id, "observed": status})
        if lane_id in LOCAL_BINARY_LANES:
            binaries = lane.get("local_binary") or {}
            expected_binaries = LOCAL_BINARY_LANES[lane_id]
            if status == "ready":
                present_names = binaries.get("present_names") or []
                if not any(name in expected_binaries for name in present_names):
                    failures.append({"check": "ready_lane_must_explain_binary", "lane_id": lane_id, "present_names": present_names, "expected": expected_binaries})
            else:
                if lane.get("blocked_reason") not in {"required_local_binary_missing", "unknown_runtime_kind"}:
                    failures.append({"check": "blocked_reason_is_local_binary_missing", "lane_id": lane_id, "observed": lane.get("blocked_reason")})
        if lane.get("evidence_state") == "ready_to_verify" and capability_status not in {"real_runtime_gated"}:
            failures.append({"check": "only_real_runtime_gated_can_be_ready_to_verify", "lane_id": lane_id, "capability_status": capability_status})
        if lane.get("report_action") not in {"allow_with_artifacts", "label_as_proxy_or_block_until_artifacts_exist"}:
            failures.append({"check": "report_action_known", "lane_id": lane_id, "observed": lane.get("report_action")})

    report_out = {
        "local_only": True,
        "success": not failures,
        "builder_contract": rel(BUILDER),
        "report_matches_current_builder_projection": report == expected_report,
        "receipts_match_current_builder_projection": receipts == expected_receipts,
        "lanes": len(lanes),
        "receipts": len(receipts),
        "expected_lanes": len(expected_report.get("lanes") or []),
        "expected_receipts": len(expected_receipts),
        "proxy_lanes_blocked": sum(1 for row in lanes if row.get("lane_id") in PROXY_LANES and row.get("status") == "blocked"),
        "ready_lanes": sum(1 for row in lanes if row.get("status") == "ready"),
        "failures": failures,
        "policy": "Validation proves the lane pack is local-signal only. It does not establish real inference, docking, or dynamics execution.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": report_out["success"],
        "lanes": report_out["lanes"],
        "failures": len(failures),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
