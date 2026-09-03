#!/usr/bin/env python3
"""Build a Stage 25 FoldX provision manifest candidate from local probe reports."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = AI_ROOT / "reports" / "ddg_local_runtime_discovery_report.json"
PROBE = AI_ROOT / "reports" / "ddg_executable_probe_report.json"
BOOTSTRAP = AI_ROOT / "reports" / "foldx_physical_smoke_bootstrap_report.json"
TECHNICAL_SMOKE_REPORT = AI_ROOT / "reports" / "stage25_foldx_technical_smoke_20260806.json"
TECHNICAL_SMOKE_VALIDATION = AI_ROOT / "reports" / "stage25_foldx_technical_smoke_validation_20260806.json"
UNBLOCK = AI_ROOT / "datasets" / "governance" / "stage25_unblock_operator_packets_20260806.jsonl"
OUTPUT = AI_ROOT / "datasets" / "governance" / "stage25_foldx_provision_manifest_candidate_20260806.jsonl"
TECHNICAL_SMOKE_DIR = "cache/advanced_features/ddg_physical_smoke/foldx/stage25_technical_smoke_20260806"

PROVISION_ROWS = [
    ("stage25_foldx_executable", "licensed_foldx_executable", "cache/external/FoldX/foldx"),
    ("stage25_foldx_parameters", "physical_smoke_artifact", "cache/advanced_features/ddg_physical_smoke/foldx/stage25/parameters.json"),
    ("stage25_foldx_input_structure_sha256", "physical_smoke_artifact", "cache/advanced_features/ddg_physical_smoke/foldx/stage25/input_structure.sha256"),
    ("stage25_foldx_mutation_list", "physical_smoke_artifact", "cache/advanced_features/ddg_physical_smoke/foldx/stage25/mutation_list.json"),
    ("stage25_foldx_ddg_table", "physical_smoke_artifact", "cache/advanced_features/ddg_physical_smoke/foldx/stage25/ddg_table.json"),
    ("stage25_foldx_runtime_log", "physical_smoke_artifact", "cache/advanced_features/ddg_physical_smoke/foldx/stage25/runtime.log"),
]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return data


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


def foldx_probe_row(probe: dict[str, Any]) -> dict[str, Any]:
    for row in probe.get("backend_rows") or []:
        if isinstance(row, dict) and row.get("backend") == "foldx":
            return row
    return {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    discovery = load_json(DISCOVERY)
    probe = load_json(PROBE)
    bootstrap = load_json(BOOTSTRAP)
    technical_smoke = load_json(TECHNICAL_SMOKE_REPORT)
    technical_validation = load_json(TECHNICAL_SMOKE_VALIDATION)
    packets = load_jsonl(UNBLOCK)
    foldx_packet = next((row for row in packets if row.get("packet_type") == "foldx_runtime_provision_unblock"), {})
    probe_row = foldx_probe_row(probe)

    missing_reason = {
        "foldx_candidate_rows": discovery.get("foldx_candidate_rows"),
        "probe_blockers": probe_row.get("blockers") or [],
        "bootstrap_blockers": bootstrap.get("blockers") or [],
        "unblock_packet_id": foldx_packet.get("packet_id"),
    }
    rows = []
    for provision_id, artifact_kind, expected_path in PROVISION_ROWS:
        local_path = AI_ROOT / expected_path
        present = local_path.exists() and local_path.is_file()
        technical_path = f"{TECHNICAL_SMOKE_DIR}/{Path(expected_path).name}" if artifact_kind == "physical_smoke_artifact" else None
        technical_local_path = AI_ROOT / technical_path if technical_path else None
        technical_present = bool(technical_local_path and technical_local_path.exists() and technical_local_path.is_file())
        technical_sha256 = sha256(technical_local_path) if technical_local_path else None
        receipted_technical_sha256 = (technical_smoke.get("artifact_sha256") or {}).get(technical_path) if technical_path else None
        rows.append({
            "provision_id": provision_id,
            "stage": 25,
            "packet_id": foldx_packet.get("packet_id") or "stage25_unblock_foldx_runtime_20260806",
            "artifact_kind": artifact_kind,
            "expected_local_path": expected_path,
            "required": True,
            "status": "present" if present else "missing",
            "present": present,
            "size_bytes": local_path.stat().st_size if present else None,
            "sha256": sha256(local_path),
            "evidence_class": "formal_runtime_provision",
            "technical_smoke_counterpart_path": technical_path,
            "technical_smoke_counterpart_present": technical_present,
            "technical_smoke_counterpart_sha256": technical_sha256,
            "technical_smoke_counterpart_checksum_matches_receipt": bool(technical_path and technical_sha256 and technical_sha256 == receipted_technical_sha256),
            "technical_smoke_validation_success": technical_validation.get("success") is True,
            "technical_smoke_can_satisfy_formal_requirement": False,
            "ready_for_runtime_receipt": False,
            "missing_reason": missing_reason,
            "formal_runtime_receipt_written": False,
            "completion_ready": False,
            "safe_for_model_claim": False,
            "release_ready": False,
            "policy": "Formal provision candidate only. Isolated technical-smoke counterparts are tracked as technical evidence but cannot satisfy or overwrite formal provision requirements, prove license approval/runtime readiness, or write a formal runtime receipt.",
        })

    OUTPUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "candidate_rows": len(rows), "foldx_candidate_rows": discovery.get("foldx_candidate_rows"), "ready_for_runtime_receipt_rows": 0}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
