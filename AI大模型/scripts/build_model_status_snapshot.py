#!/usr/bin/env python3
"""Build the canonical, fail-closed KWB model status snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
OUT = AI_ROOT / "reports" / "model_status.json"
SOURCES = {
    "multitask": "reports/multitask_training_readiness_report.json",
    "execution": "reports/five_head_training_execution_contract_report.json",
    "features": "reports/advanced_model_feature_contract_validation_report.json",
    "pretraining": "reports/sequence_pretraining_continuous_selection.json",
    "ddg": "reports/ddg_backend_readiness_report.json",
    "unlock": "reports/model_quality_unlock_requirements_report.json",
    "production": "reports/production_model_gate_20260829.json",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def find_backend(report: dict[str, Any], name: str) -> dict[str, Any]:
    for row in report.get("backends") or []:
        if isinstance(row, dict) and row.get("backend") == name:
            return row
    return {}


def legacy_thermompnn_ready(unlock: dict[str, Any]) -> bool | None:
    for row in unlock.get("requirements") or []:
        if isinstance(row, dict) and row.get("requirement_id") == "MQ-U003":
            state = row.get("current_state") if isinstance(row.get("current_state"), dict) else {}
            value = state.get("thermompnn_ready")
            return value if isinstance(value, bool) else None
    return None


def build_snapshot(base: Path = AI_ROOT) -> dict[str, Any]:
    paths = {name: base / relative for name, relative in SOURCES.items()}
    reports = {name: load_json(path) for name, path in paths.items()}
    missing_sources = [SOURCES[name] for name, report in reports.items() if not report]

    multitask = reports["multitask"]
    execution = reports["execution"]
    features = reports["features"]
    pretraining = reports["pretraining"]
    ddg = reports["ddg"]
    unlock = reports["unlock"]
    production = reports["production"]

    head_source = multitask.get("heads") if isinstance(multitask.get("heads"), dict) else {}
    heads = {
        name: {
            "label_rows": as_int(row.get("rows")),
            "minimum_rows": as_int(row.get("minimum_rows")) or 100,
            "ready": row.get("ready") is True,
        }
        for name, row in head_source.items()
        if isinstance(row, dict)
    }
    ready_families = (
        (features.get("feature_contract") or {}).get("ready_family_counts")
        if isinstance(features.get("feature_contract"), dict)
        else {}
    )
    ready_families = ready_families if isinstance(ready_families, dict) else {}

    thermompnn = find_backend(ddg, "thermompnn")
    thermompnn_execution_ready = thermompnn.get("ready_for_execution") is True
    thermompnn_legacy_ready = legacy_thermompnn_ready(unlock)
    conflicts: list[dict[str, Any]] = []
    if (
        thermompnn_legacy_ready is not None
        and thermompnn_legacy_ready != thermompnn_execution_ready
    ):
        conflicts.append(
            {
                "key": "thermompnn_ready",
                "current_value": thermompnn_execution_ready,
                "current_source": SOURCES["ddg"],
                "stale_value": thermompnn_legacy_ready,
                "stale_source": SOURCES["unlock"],
                "resolution": "use dimensioned current ddG readiness; do not use legacy aggregate boolean",
            }
        )

    strict_rows = as_int((production.get("evidence") or {}).get("strict_supervised_rows"))
    ready_head_count = as_int(multitask.get("ready_head_count"))
    training_allowed = (
        execution.get("training_execution_allowed") is True
        and multitask.get("training_execution_allowed") is True
    )
    production_ready = production.get("production_ready") is True
    snapshot = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "local_only": True,
        "canonical_status_source": True,
        "sources": {
            name: {
                "path": SOURCES[name],
                "present": bool(reports[name]),
                "sha256": sha256(path),
            }
            for name, path in paths.items()
        },
        "stages": {
            "rule_mvp": {
                "status": "baseline_only",
                "safe_for_model_claim": False,
            },
            "pretraining": {
                "status": (
                    "completed_pretraining_only"
                    if pretraining.get("integrity_pass") is True
                    else "blocked_or_missing"
                ),
                "selected_checkpoint": pretraining.get("selected_checkpoint"),
                "sequence_count": as_int(pretraining.get("sequence_count")),
                "safe_for_supervised_training": False,
                "safe_for_model_claim": False,
            },
            "research_training": {
                "status": "blocked_head_thresholds_not_met" if not training_allowed else "eligible",
                "ready_head_count": ready_head_count,
                "training_execution_allowed": training_allowed,
                "safe_for_model_claim": False,
            },
            "production": {
                "status": "ready" if production_ready else "blocked",
                "ready": production_ready,
                "strict_supervised_rows": strict_rows,
                "safe_for_model_claim": production_ready,
                "release_ready": production_ready and production.get("evidence", {}).get("release_ready") is True,
            },
        },
        "heads": heads,
        "features": {
            family: {"ready_rows": as_int(rows), "input_only": True, "label_rows": 0}
            for family, rows in ready_families.items()
        },
        "tools": {
            "thermompnn": {
                "installed": thermompnn.get("install_ready") is True,
                "runtime_ready": thermompnn.get("runtime_ready") is True,
                "data_ready": thermompnn.get("data_ready") is True,
                "model_weight_ready": thermompnn.get("model_weight_ready") is True,
                "execution_ready": thermompnn_execution_ready,
                "claim_eligible": False,
                "commercial_status": thermompnn.get("commercial_status"),
            }
        },
        "consistency": {
            "missing_sources": missing_sources,
            "conflicts": conflicts,
            "feature_rows_counted_as_labels": 0,
        },
        "next_actions": [
            "obtain reviewed, provenance-backed labels with explicit assay conditions",
            "reach per-head sample, replicate, and independent-group thresholds",
            "run research shadow evaluation before any production model claim",
        ],
        "safe_for_model_claim": production_ready,
        "release_ready": production_ready and production.get("evidence", {}).get("release_ready") is True,
        "policy": (
            "This is the canonical status projection. Rule baselines, unlabeled pretraining, "
            "features, proxy tools, and research smoke runs never count as production labels "
            "or model-quality evidence."
        ),
    }
    snapshot["features"].setdefault(
        "structure_graph",
        {"ready_rows": as_int(ddg.get("reviewed_structure_rows")), "input_only": True, "label_rows": 0},
    )
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Build canonical KWB model status snapshot")
    parser.add_argument("--base", type=Path, default=AI_ROOT)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    snapshot = build_snapshot(args.base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "production_ready": snapshot["stages"]["production"]["ready"],
                "ready_head_count": snapshot["stages"]["research_training"]["ready_head_count"],
                "conflict_count": len(snapshot["consistency"]["conflicts"]),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
