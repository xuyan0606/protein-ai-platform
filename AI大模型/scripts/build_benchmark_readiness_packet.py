#!/usr/bin/env python3
"""Build local benchmark readiness packets from the current benchmark gap reports.

The builder is intentionally non-mutating with respect to benchmark intake,
score-cache manifests, training labels, model claims, and release flags. It
only creates governance packets and a report describing the observed state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKETS = AI_ROOT / "datasets" / "governance" / "benchmark_readiness_packets.jsonl"
DEFAULT_REPORT = AI_ROOT / "reports" / "benchmark_readiness_packet_report.json"
DEFAULT_MARKDOWN = AI_ROOT / "reports" / "benchmark_readiness_packets.md"

HEAD_ORDER = (
    "mutation_rank",
    "stability",
    "activity_risk",
    "substrate_fit",
    "assay_success",
)

INPUTS = {
    "benchmark_matrix_report": AI_ROOT / "reports" / "benchmark_matrix_report.json",
    "benchmark_acquisition_plan": AI_ROOT / "datasets" / "benchmark" / "benchmark_acquisition_plan.jsonl",
    "benchmark_score_cache_manifest": AI_ROOT / "reports" / "benchmark_score_cache_manifest.json",
    "benchmark_score_cache_intake_report": AI_ROOT / "reports" / "benchmark_score_cache_intake_report.json",
    "benchmark_score_cache_validation_report": AI_ROOT / "reports" / "benchmark_score_cache_validation_report.json",
    "benchmark_coverage_dashboard": AI_ROOT / "reports" / "benchmark_coverage_dashboard.json",
    "benchmark_gap_queue": AI_ROOT / "datasets" / "benchmark" / "benchmark_gap_queue.jsonl",
    "five_head_benchmark_gap_actions": AI_ROOT / "datasets" / "governance" / "five_head_benchmark_gap_actions.jsonl",
    "five_head_benchmark_gap_plan_report": AI_ROOT / "reports" / "five_head_benchmark_gap_plan_report.json",
    "benchmark_score_cache_intake": AI_ROOT / "datasets" / "benchmark" / "benchmark_score_cache_intake.local.jsonl",
}

REQUIRED_CACHE_ARTIFACTS = (
    "local_dataset_uri",
    "dataset_sha256",
    "split_definition_uri",
    "split_sha256",
    "scorecard_uri",
    "scorecard_sha256",
    "metric_report_uri",
    "metric_sha256",
)

POLICY = (
    "Benchmark readiness packet only. It is a local execution contract for resolving an "
    "invalid benchmark gap. It does not download data, accept licenses, write score-cache "
    "intake, update a manifest, create scores, open model claims, change training labels, "
    "change release flags, or grant release readiness."
)

BENCHMARK_ACQUISITION_POLICY: dict[tuple[str, str], dict[str, Any]] = {
    ("mutation_rank", "ProteinGym"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "ProteinGym source/reference package and local file index are present; a KWB scorecard and leakage-safe intake row are still absent.",
        "source_paths": [
            "reports/proteingym_local_source_report.json",
            "reports/proteingym_local_source_manifest.json",
            "datasets/benchmark/proteingym_local_source_files.jsonl",
            "cache/external/ProteinGym/LICENSE",
        ],
    },
    ("mutation_rank", "FLIP/FLIP2-style protein/family/time split"): {
        "acquisition_mode": "external_source_required",
        "download_required": True,
        "rationale": "No local FLIP/FLIP2 source or score-cache contract is present; an operator must acquire or supply an authorized local snapshot before scoring.",
        "source_paths": [],
    },
    ("mutation_rank", "KWB strict mutation holdout"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "Local strict-holdout dataset, split, scorecard, and metric artifacts exist, but the intake candidate was rejected because leakage_check_status is failed.",
        "source_paths": [
            "cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/dataset.jsonl",
            "cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/split_definition.json",
            "cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/scorecard.json",
            "cache/advanced_features/benchmarks/kwb_strict_mutation_holdout/metric_report.json",
            "datasets/benchmark/benchmark_score_cache_intake.local.jsonl",
            "reports/benchmark_score_cache_intake_report.json",
        ],
    },
    ("stability", "ThermoMPNN comparison"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "ThermoMPNN source, model, and local-source evidence are present; a benchmark dataset/split/scorecard intake row is still absent.",
        "source_paths": [
            "reports/thermompnn_local_source_report.json",
            "reports/thermompnn_local_source_manifest.json",
            "cache/external/ThermoMPNN/README.md",
        ],
    },
    ("stability", "ATOM3D MSP"): {
        "acquisition_mode": "external_source_required",
        "download_required": True,
        "rationale": "No local ATOM3D MSP dataset or score-cache contract is present; acquire an authorized local snapshot before scoring.",
        "source_paths": [],
    },
    ("stability", "FireProt/ProTherm reviewed stability set"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "FireProtDB/ProTherm candidate and leakage-review artifacts are local, but reviewed benchmark acceptance and score-cache intake are not complete.",
        "source_paths": [
            "reports/fireprot_reviewed_import_candidate_report.json",
            "reports/fireprot_curated_import_leakage_review_report.json",
            "datasets/curation/fireprot_reviewed_import_candidates.jsonl",
            "cache/external/FireProtDB",
        ],
    },
    ("activity_risk", "KWB plate-level wet-lab feedback"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "Local plate-feedback rows and validation reports are present; benchmark scorecard registration remains separate from feedback-label governance.",
        "source_paths": [
            "datasets/feedback/experiment_feedback_plate.local.jsonl",
            "reports/experiment_feedback_plate_intake_validation_report.json",
            "reports/experiment_feedback_intake_validation_report.json",
        ],
    },
    ("activity_risk", "CatPred/GotEnzymes predicted reference only"): {
        "acquisition_mode": "external_source_required",
        "download_required": True,
        "rationale": "No local CatPred/GotEnzymes reference snapshot or score-cache contract is present; acquire only an authorized reference package and keep it evaluation-only.",
        "source_paths": [],
    },
    ("substrate_fit", "PDBbind/CASF/D3R-style affinity or pose benchmark"): {
        "acquisition_mode": "external_source_required",
        "download_required": True,
        "rationale": "No local affinity/pose benchmark snapshot or score-cache contract is present; acquisition requires an explicit local source and license record.",
        "source_paths": [],
    },
    ("substrate_fit", "PoseBusters-style pose plausibility"): {
        "acquisition_mode": "external_source_required",
        "download_required": True,
        "rationale": "No local PoseBusters-style dataset or score-cache contract is present; acquire only after source and license scope are recorded.",
        "source_paths": [],
    },
    ("substrate_fit", "reviewed substrate identity set"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "This is an internal reviewed-substrate contract; no external download is required, but reviewed identity/condition/lineage evidence is still missing.",
        "source_paths": [
            "reports/substrate_fit_label_gap_plan_report.json",
            "datasets/governance/substrate_fit_label_gap_actions.jsonl",
            "reports/substrate_fit_hard_gate_operator_packet_report.json",
        ],
    },
    ("assay_success", "KWB plate-level feedback"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "Local plate-feedback rows and QC/review reports are present; replicate/QC scorecard artifacts are not accepted in the benchmark cache.",
        "source_paths": [
            "datasets/feedback/experiment_feedback_plate.local.jsonl",
            "reports/experiment_feedback_plate_intake_validation_report.json",
            "reports/wet_lab_mutant_library_feedback_qc_matrix_report.json",
        ],
    },
    ("assay_success", "replicate consistency"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "Replicate consistency is an internal assay contract and requires local reviewed replicate/QC records; no external download is required.",
        "source_paths": [
            "datasets/feedback/experiment_feedback_plate.local.jsonl",
            "reports/wet_lab_mutant_library_feedback_qc_matrix_report.json",
            "reports/experiment_feedback_plate_intake_backlog_report.json",
        ],
    },
    ("assay_success", "QC fail-rate calibration"): {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "QC fail-rate calibration is an internal assay contract and requires local reviewed QC outcomes; no external download is required.",
        "source_paths": [
            "reports/wet_lab_mutant_library_feedback_qc_matrix_report.json",
            "reports/experiment_feedback_plate_intake_validation_report.json",
            "reports/experiment_feedback_plate_intake_backlog_report.json",
        ],
    },
}


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text[:80] or "benchmark"


def snapshot_inputs() -> list[dict[str, Any]]:
    snapshot = []
    for name, path in INPUTS.items():
        exists = path.exists()
        snapshot.append({
            "name": name,
            "path": relative(path),
            "exists": exists,
            "sha256": sha256(path) if exists and path.is_file() else "",
            "size_bytes": path.stat().st_size if exists and path.is_file() else None,
        })
    return snapshot


def evidence(paths: list[str]) -> list[dict[str, Any]]:
    rows = []
    for value in paths:
        path = AI_ROOT / value
        exists = path.exists()
        rows.append({
            "path": value,
            "exists": exists,
            "sha256": sha256(path) if exists and path.is_file() else "",
            "size_bytes": path.stat().st_size if exists and path.is_file() else None,
        })
    return rows


def index_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row.get("head")), str(row.get("benchmark_name"))): row
        for row in rows
        if isinstance(row.get("head"), str) and isinstance(row.get("benchmark_name"), str)
    }


def matrix_index(matrix: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for head_row in matrix.get("heads") or []:
        if not isinstance(head_row, dict):
            continue
        head = head_row.get("head")
        for benchmark_name in head_row.get("required_benchmarks") or []:
            if isinstance(head, str) and isinstance(benchmark_name, str):
                indexed[(head, benchmark_name)] = head_row
    return indexed


def coverage_index(dashboard: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for head_row in dashboard.get("heads") or []:
        if not isinstance(head_row, dict):
            continue
        head = head_row.get("head")
        for benchmark_name in head_row.get("missing_benchmarks") or []:
            if isinstance(head, str) and isinstance(benchmark_name, str):
                indexed[(head, benchmark_name)] = {
                    "head": head,
                    "benchmark_name": benchmark_name,
                    "gap_queue_id": head_row.get("gap_queue_id"),
                    "head_status": head_row.get("status"),
                    "head_error_counts": head_row.get("error_counts") or {},
                    "valid": False,
                    "errors": head_row.get("error_counts") or {},
                }
    return indexed


def gap_queue_item_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for head_row in rows:
        head = head_row.get("head")
        for item in head_row.get("benchmark_gap_items") or []:
            if isinstance(head, str) and isinstance(item, dict) and isinstance(item.get("benchmark_name"), str):
                indexed[(head, item["benchmark_name"])] = item
    return indexed


def gap_plan_index(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for head_row in report.get("heads") or []:
        if not isinstance(head_row, dict):
            continue
        head = head_row.get("head")
        for item in head_row.get("benchmark_rows") or []:
            if isinstance(head, str) and isinstance(item, dict) and isinstance(item.get("benchmark_name"), str):
                indexed[(head, item["benchmark_name"])] = item
    return indexed


def gap_action_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("head")): row
        for row in rows
        if isinstance(row.get("head"), str)
    }


def source_discrepancies(
    dashboard: dict[str, Any],
    action_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    coverage_by_head = {
        str(row.get("head")): list(row.get("missing_benchmarks") or [])
        for row in dashboard.get("heads") or []
        if isinstance(row, dict) and isinstance(row.get("head"), str)
    }
    actions_by_head = gap_action_index(action_rows)
    discrepancies = []
    for head in HEAD_ORDER:
        expected = coverage_by_head.get(head, [])
        observed = list(actions_by_head.get(head, {}).get("missing_benchmarks") or [])
        if observed != expected:
            discrepancies.append({
                "head": head,
                "authoritative_missing_benchmarks": expected,
                "gap_action_missing_benchmarks": observed,
                "reason": "gap action summary does not match current coverage dashboard",
            })
    return discrepancies


def candidate_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return index_rows(rows)


def current_candidate(
    head: str,
    benchmark_name: str,
    intake_by_key: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    row = intake_by_key.get((head, benchmark_name))
    if not row:
        return None
    return {
        "source_file": relative(INPUTS["benchmark_score_cache_intake"]),
        "status": "rejected_candidate",
        "license_review_status": row.get("license_review_status"),
        "leakage_check_status": row.get("leakage_check_status"),
        "dataset_version": row.get("dataset_version"),
        "artifact_refs": {
            key: row.get(key)
            for key in (
                "local_dataset_uri",
                "dataset_sha256",
                "split_definition_uri",
                "split_sha256",
                "scorecard_uri",
                "scorecard_sha256",
                "metric_report_uri",
                "metric_sha256",
            )
            if row.get(key)
        },
        "rejection_reason": "leakage_check_not_passed",
        "score_values": None,
    }


def build_receipt(
    packet_id: str,
    receipt_type: str,
    action: str,
    required_outputs: list[str],
    commands: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipt = {
        "receipt_id": f"{packet_id}::{receipt_type}",
        "receipt_type": receipt_type,
        "status": "blocked",
        "action": action,
        "required_outputs": required_outputs,
        "operator_commands": commands,
        "receipt_input": None,
        "completion_ready": False,
        "no_fabricated_scores": True,
    }
    if extra:
        receipt.update(extra)
    return receipt


def build_packet(
    execution_order: int,
    key: tuple[str, str],
    sources: dict[str, Any],
    matrix_by_key: dict[tuple[str, str], dict[str, Any]],
    plan_by_key: dict[tuple[str, str], dict[str, Any]],
    manifest_by_key: dict[tuple[str, str], dict[str, Any]],
    validation_by_key: dict[tuple[str, str], dict[str, Any]],
    coverage_by_key: dict[tuple[str, str], dict[str, Any]],
    queue_by_key: dict[tuple[str, str], dict[str, Any]],
    gap_plan_by_key: dict[tuple[str, str], dict[str, Any]],
    intake_by_key: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    head, benchmark_name = key
    packet_id = f"benchmark-readiness-{head}-{slug(benchmark_name)}"
    matrix = matrix_by_key[key]
    plan = plan_by_key.get(key, {})
    manifest = manifest_by_key.get(key, {})
    validation = validation_by_key.get(key, {})
    coverage = coverage_by_key.get(key, {})
    queue_item = queue_by_key.get(key, {})
    gap_plan = gap_plan_by_key.get(key, {})
    policy = BENCHMARK_ACQUISITION_POLICY.get(key, {
        "acquisition_mode": "local_contract_only",
        "download_required": False,
        "rationale": "No benchmark-specific acquisition shortcut is permitted; create a local contract and require human review.",
        "source_paths": [],
    })

    validation_errors = validation.get("errors")
    if not isinstance(validation_errors, list):
        validation_errors = ["cache_validation_record_missing"]

    current_observation = {
        "matrix": {
            "head": head,
            "benchmark_name": benchmark_name,
            "training_ready": matrix.get("training_ready") is True,
            "benchmark_data_ready": matrix.get("benchmark_data_ready") is True,
            "scorecard_ready": matrix.get("scorecard_ready") is True,
        },
        "acquisition": {
            key: plan.get(key)
            for key in (
                "acquisition_status",
                "license_review_status",
                "local_dataset_uri",
                "checksum",
                "split_strategy",
                "leakage_check_status",
                "scorecard_status",
            )
        },
        "manifest": {
            key: manifest.get(key)
            for key in (
                "status",
                "dataset_version",
                "local_dataset_uri",
                "dataset_sha256",
                "split_definition_uri",
                "split_sha256",
                "scorecard_uri",
                "scorecard_sha256",
                "metric_report_uri",
                "metric_sha256",
                "leakage_check_status",
            )
        },
        "cache_validation": {
            "valid": validation.get("valid") is True and not validation_errors,
            "errors": [str(error) for error in validation_errors],
        },
        "coverage_gap": {
            "gap_id": queue_item.get("gap_id"),
            "status": queue_item.get("status"),
            "missing_requirements": queue_item.get("missing_requirements") or [],
            "missing_cache_artifacts": queue_item.get("missing_cache_artifacts") or [],
            "cache_validation_errors": queue_item.get("cache_validation_errors") or [],
        },
        "gap_plan": {
            "status": gap_plan.get("status"),
            "blockers": gap_plan.get("blockers") or [],
            "required_operator_actions": gap_plan.get("required_operator_actions") or [],
            "claim_gate": gap_plan.get("claim_gate"),
        },
        "intake_candidate": current_candidate(head, benchmark_name, intake_by_key),
    }

    acquisition_receipt = build_receipt(
        packet_id,
        "acquisition",
        (
            "Register an authorized local source or local-only contract; do not download from this packet. "
            "For external_source_required rows, an operator must acquire the source separately and record it."
        ),
        [
            "configured acquisition plan row",
            "authorized local source or explicit local-only contract",
            "local dataset URI",
            "dataset SHA-256",
            "license review status",
        ],
        [
            "Review the source evidence listed in acquisition_receipt.source_evidence.",
            "Write only a human-reviewed acquisition/intake record after the source and license scope are verified.",
            "Do not run a downloader from this packet.",
        ],
        {
            "acquisition_mode": policy["acquisition_mode"],
            "download_required": policy["download_required"],
            "download_executed": False,
            "download_authorized_by_packet": False,
            "rationale": policy["rationale"],
            "source_evidence": evidence(policy["source_paths"]),
            "target_fields": [
                "acquisition_status=configured",
                "license_review_status=approved_for_benchmark_only|approved_for_model_evaluation",
                "local_dataset_uri",
                "dataset_sha256",
            ],
        },
    )

    candidate = current_observation["intake_candidate"]
    score_receipt = build_receipt(
        packet_id,
        "score",
        (
            "Produce or register real dataset/split/scorecard/metric artifacts only after acquisition, "
            "license, and leakage gates pass; never fill score values in this packet."
        ),
        [
            "dataset_version",
            "dataset/split/scorecard/metric artifact files",
            "SHA-256 for each artifact",
            "leakage_check_status=passed",
            "reviewer and reviewed_at",
            "human acceptance receipt",
        ],
        [
            "Use only real local artifacts and record their SHA-256 values.",
            "Do not infer, copy, or fabricate benchmark metric values.",
            "After all gates pass, append a reviewed row to datasets/benchmark/benchmark_score_cache_intake.local.jsonl.",
        ],
        {
            "target_intake": "datasets/benchmark/benchmark_score_cache_intake.local.jsonl",
            "required_intake_fields": [
                "head",
                "benchmark_name",
                "dataset_version",
                *REQUIRED_CACHE_ARTIFACTS,
                "license_review_status",
                "leakage_check_status",
                "reviewer",
                "reviewed_at",
                "human_acceptance_receipt",
            ],
            "candidate_artifacts": candidate.get("artifact_refs") if candidate else {},
            "candidate_status": candidate.get("status") if candidate else "none",
            "candidate_rejection_reason": candidate.get("rejection_reason") if candidate else None,
            "score_values": None,
            "metric_values": None,
            "score_values_prohibited": True,
        },
    )

    validation_receipt = build_receipt(
        packet_id,
        "validation",
        "Rerun the existing benchmark validators and require every upstream report to agree before closure.",
        [
            "valid benchmark score-cache validation record",
            "coverage dashboard row with valid=1 and missing=0",
            "gap queue item removed by regenerated coverage report",
            "readiness packet regenerated from the new source snapshot",
        ],
        [
            "python3 scripts/apply_benchmark_score_cache_intake.py",
            "python3 scripts/validate_benchmark_score_cache.py",
            "python3 scripts/build_benchmark_coverage_dashboard.py",
            "python3 scripts/validate_benchmark_coverage_dashboard.py",
            "python3 scripts/validate_benchmark_readiness_packet.py --require-ready",
        ],
        {
            "upstream_validation_errors": [str(error) for error in validation_errors],
            "current_coverage_status": coverage.get("head_status"),
            "current_gap_id": coverage.get("gap_queue_id"),
            "required_consistency_checks": [
                "matrix/acquisition/manifest/validation identity matches head and benchmark",
                "all four artifact paths exist and hashes match",
                "license review is approved for the intended benchmark scope",
                "leakage check is passed",
                "scorecard and metric report are real local artifacts",
                "human acceptance receipt is present",
                "no benchmark row is used as a KWB training label",
            ],
        },
    )

    required_actions = [
        "resolve acquisition receipt",
        "resolve score receipt with real artifacts and no fabricated score",
        "resolve validation receipt",
        "regenerate the packet after upstream reports change",
    ]
    if policy["download_required"]:
        required_actions.insert(1, "acquire or receive an authorized local source outside this packet")
    if candidate:
        required_actions.insert(1, "repair the rejected local candidate and rerun its leakage review")

    return {
        "schema_version": "1.0.0",
        "packet_id": packet_id,
        "gap_id": queue_item.get("gap_id") or f"benchmark_gap::{head}::{slug(benchmark_name).replace('-', '_')}",
        "execution_order": execution_order,
        "priority": "P0",
        "workstream": "benchmark_readiness",
        "head": head,
        "benchmark_name": benchmark_name,
        "status": "blocked",
        "source_snapshot": {"inputs": sources},
        "current_observation": current_observation,
        "acquisition_receipt": acquisition_receipt,
        "score_receipt": score_receipt,
        "validation_receipt": validation_receipt,
        "required_operator_actions": required_actions,
        "completion_condition": (
            "All three receipts must contain human-reviewed evidence, upstream cache validation must be valid, "
            "and the regenerated coverage/gap reports must show this benchmark as valid before this packet can close."
        ),
        "completion_ready": False,
        "requires_human_input": True,
        "safe_for_training_import": False,
        "benchmark_metric_claim_allowed": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "write_benchmark_score_cache_intake_allowed": False,
        "manifest_update_allowed": False,
        "model_claim_allowed": False,
        "training_labels_modified": False,
        "release_flags_modified": False,
        "policy": POLICY,
    }


def markdown(report: dict[str, Any], packets: list[dict[str, Any]]) -> str:
    lines = [
        "# Benchmark Readiness Packets",
        "",
        "## Status",
        "",
        f"- Packet rows: `{report['summary']['packet_rows']}`",
        f"- Invalid gaps represented: `{report['summary']['invalid_gap_rows']}`",
        f"- Local-contract-only rows: `{report['summary']['local_contract_only_rows']}`",
        f"- External-source-required rows: `{report['summary']['external_source_required_rows']}`",
        f"- Completion-ready rows: `{report['summary']['completion_ready_rows']}`",
        f"- Score values recorded: `{report['summary']['score_values_recorded']}`",
        f"- Source discrepancy notes: `{len(report['source_discrepancies'])}`",
        "- Model claims, training labels, release flags, and existing score-cache artifacts were not modified by packet generation.",
        "",
        "## Packet Matrix",
        "",
        "| Order | Head | Benchmark | Acquisition | Download executed | Current cache validation | Candidate | Completion |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for packet in packets:
        acquisition = packet["acquisition_receipt"]
        observation = packet["current_observation"]
        candidate = observation.get("intake_candidate")
        lines.append(
            "| {order} | {head} | {benchmark} | {mode} | {download} | {validation} | {candidate} | {completion} |".format(
                order=packet["execution_order"],
                head=packet["head"],
                benchmark=packet["benchmark_name"],
                mode=acquisition["acquisition_mode"],
                download=acquisition["download_executed"],
                validation=observation["cache_validation"]["valid"],
                candidate="rejected" if candidate else "none",
                completion=packet["completion_ready"],
            )
        )
    lines.extend(
        [
            "",
            "## Execution Order",
            "",
            "1. Resolve the acquisition receipt using only authorized local source evidence or a separately approved local source.",
            "2. Resolve the score receipt with real dataset/split/scorecard/metric artifacts and SHA-256 values.",
            "3. Run the existing cache, coverage, and this packet validator; regenerate the packet after source reports change.",
            "",
            "## Fail-Closed Policy",
            "",
            report["policy"],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark readiness packets")
    parser.add_argument("--packets", type=Path, default=DEFAULT_PACKETS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    matrix = load_json(INPUTS["benchmark_matrix_report"])
    acquisition = load_jsonl(INPUTS["benchmark_acquisition_plan"])
    manifest = load_json(INPUTS["benchmark_score_cache_manifest"])
    intake_report = load_json(INPUTS["benchmark_score_cache_intake_report"])
    validation = load_json(INPUTS["benchmark_score_cache_validation_report"])
    dashboard = load_json(INPUTS["benchmark_coverage_dashboard"])
    gap_queue = load_jsonl(INPUTS["benchmark_gap_queue"])
    gap_actions = load_jsonl(INPUTS["five_head_benchmark_gap_actions"])
    gap_plan = load_json(INPUTS["five_head_benchmark_gap_plan_report"])
    intake = load_jsonl(INPUTS["benchmark_score_cache_intake"])

    matrix_by_key = matrix_index(matrix)
    plan_by_key = index_rows(acquisition)
    manifest_by_key = index_rows(manifest.get("rows") or [])
    validation_by_key = index_rows(validation.get("records") or [])
    coverage_by_key = coverage_index(dashboard)
    queue_by_key = gap_queue_item_index(gap_queue)
    gap_plan_by_key = gap_plan_index(gap_plan)
    intake_by_key = candidate_index(intake)
    source_snapshot = snapshot_inputs()
    discrepancies = source_discrepancies(dashboard, gap_actions)

    keys = [
        key
        for key in matrix_by_key
        if key in coverage_by_key or not (validation_by_key.get(key) or {}).get("valid")
    ]

    packets = [
        build_packet(
            index,
            key,
            source_snapshot,
            matrix_by_key,
            plan_by_key,
            manifest_by_key,
            validation_by_key,
            coverage_by_key,
            queue_by_key,
            gap_plan_by_key,
            intake_by_key,
        )
        for index, key in enumerate(keys, start=1)
        if key in matrix_by_key
    ]

    missing_source_inputs = [
        item["name"] for item in source_snapshot if not item["exists"]
    ]
    summary = {
        "packet_rows": len(packets),
        "invalid_gap_rows": sum(
            1
            for packet in packets
            if packet["current_observation"]["cache_validation"]["valid"] is False
        ),
        "local_contract_only_rows": sum(
            1
            for packet in packets
            if packet["acquisition_receipt"]["acquisition_mode"] == "local_contract_only"
        ),
        "external_source_required_rows": sum(
            1
            for packet in packets
            if packet["acquisition_receipt"]["acquisition_mode"] == "external_source_required"
        ),
        "completion_ready_rows": sum(1 for packet in packets if packet["completion_ready"]),
        "score_values_recorded": sum(
            1
            for packet in packets
            if packet["score_receipt"].get("score_values") not in (None, {})
            or packet["score_receipt"].get("metric_values") not in (None, {})
        ),
        "packets_by_head": dict(Counter(packet["head"] for packet in packets)),
    }
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "status": "blocked",
        "inputs": {name: relative(path) for name, path in INPUTS.items()},
        "outputs": {
            "packets": relative(args.packets),
            "report": relative(args.report),
            "markdown": relative(args.markdown),
        },
        "source_input_missing": missing_source_inputs,
        "source_discrepancies": discrepancies,
        "summary": summary,
        "packet_ids": [packet["packet_id"] for packet in packets],
        "ready_for_model_claim": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "training_labels_modified": False,
        "release_flags_modified": False,
        "write_benchmark_score_cache_intake_allowed": False,
        "manifest_update_allowed": False,
        "policy": POLICY,
    }

    write_jsonl(args.packets, packets)
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
                "packet_rows": summary["packet_rows"],
                "invalid_gap_rows": summary["invalid_gap_rows"],
                "completion_ready_rows": summary["completion_ready_rows"],
                "score_values_recorded": summary["score_values_recorded"],
                "output": str(args.report),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
