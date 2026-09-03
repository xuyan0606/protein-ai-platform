#!/usr/bin/env python3
"""Run a reviewed-structure PyRosetta runtime smoke and write auditable artifacts.

This is a bootstrap smoke used to prove local PyRosetta runtime/init/scoring
before the formal runtime receipt is written. It is not a training-label import,
not a model-quality claim, and not a production ddG protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ddg_backend_config import default_ddg_config_path
from ddg_python_module_discovery import add_local_module_paths


AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = default_ddg_config_path()
STRUCTURE_MAPPINGS = AI_ROOT / "datasets" / "curation" / "structure_chain_mappings_curated.jsonl"
LICENSE_REPORT = AI_ROOT / "reports" / "external_license_review_decision_validation_report.json"
INSTALL_PROBE = AI_ROOT / "reports" / "pyrosetta_local_install_probe_report.json"
OUT_REPORT = AI_ROOT / "reports" / "pyrosetta_physical_smoke_bootstrap_report.json"
OUT_MD = AI_ROOT / "reports" / "pyrosetta_physical_smoke_bootstrap.md"
SMOKE_DIR = AI_ROOT / "cache" / "advanced_features" / "ddg_physical_smoke" / "pyrosetta" / "10MH_A_T10A_bootstrap"
REQUIRED_ARTIFACTS = [
    "parameters.json",
    "input_structure.sha256",
    "mutation_list.json",
    "ddg_table.json",
    "runtime.log",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(AI_ROOT))
    except ValueError:
        return str(path)


def find_structure(structure_id: str) -> dict[str, Any]:
    for row in load_jsonl(STRUCTURE_MAPPINGS):
        if row.get("structure_id") == structure_id and row.get("usable_for_coordinate_features") is True:
            return row
    raise RuntimeError(f"reviewed structure mapping not found or not usable: {structure_id}")


def license_local_eval_approved(report: dict[str, Any]) -> bool:
    for row in report.get("records") or []:
        if (
            isinstance(row, dict)
            and row.get("review_item_id") == "foreign_tool:pyrosetta"
            and row.get("valid") is True
            and row.get("approved_for_local_evaluation") is True
        ):
            return True
    return False


def write_artifacts(
    output_dir: Path,
    structure: dict[str, Any],
    mutation: dict[str, Any],
    runtime: dict[str, Any],
    ddg_table: dict[str, Any],
    runtime_log: dict[str, Any],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    structure_path = Path(str(structure["actual_cache_path"]))
    parameters = {
        "backend": "pyrosetta",
        "protocol_name": "minimal_scorefxn_single_mutation_smoke",
        "scope": "runtime_smoke_only_not_training_label",
        "structure_id": structure.get("structure_id"),
        "chain_id": structure.get("selected_chain_id"),
        "structure_path": rel(structure_path),
        "structure_sha256": structure.get("sha256"),
        "sequence_to_structure_mapping_status": structure.get("sequence_to_structure_mapping_status"),
        "mutation": mutation,
        "runtime": runtime,
        "negative_ddg_is_stabilizing": True,
        "ddg_units": "Rosetta Energy Units (REU), not kcal/mol",
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
    }
    (output_dir / "parameters.json").write_text(json.dumps(parameters, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "input_structure.sha256").write_text(sha256_file(structure_path) + "\n", encoding="utf-8")
    (output_dir / "mutation_list.json").write_text(json.dumps([mutation], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "ddg_table.json").write_text(json.dumps(ddg_table, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "runtime.log").write_text(json.dumps(runtime_log, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {rel(output_dir / name): sha256_file(output_dir / name) for name in REQUIRED_ARTIFACTS}


def run_pyrosetta_smoke(structure: dict[str, Any], mutation: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    backend_cfg = ((config.get("backends") or {}).get("pyrosetta") or {})
    install_path = backend_cfg.get("install_path") or "cache/external/PyRosetta/python"
    init_options = ((backend_cfg.get("default_parameters") or {}).get("pyrosetta_init_options") or "-mute all")
    added_paths = add_local_module_paths([install_path])
    import pyrosetta  # type: ignore
    from pyrosetta.toolbox.mutants import mutate_residue  # type: ignore

    structure_path = Path(str(structure["actual_cache_path"]))
    chain_id = str(structure.get("selected_chain_id") or "A")
    position = int(mutation["mutation_position"])
    mutant = str(mutation["mutant"])[:1]

    pyrosetta.init(init_options)
    pose = pyrosetta.pose_from_pdb(str(structure_path))
    pose_index = pose.pdb_info().pdb2pose(chain_id, position)
    if pose_index <= 0:
        raise RuntimeError(f"could not map chain {chain_id} residue {position} to pose index")
    observed_wt = pose.residue(pose_index).name1()
    if observed_wt != mutation["wild_type"]:
        raise RuntimeError(f"WT mismatch at {chain_id}{position}: observed {observed_wt}, expected {mutation['wild_type']}")

    scorefxn = pyrosetta.get_fa_scorefxn()
    wild_score = float(scorefxn(pose))
    mutant_pose = pose.clone()
    mutate_residue(mutant_pose, pose_index, mutant)
    mutant_score = float(scorefxn(mutant_pose))
    ddg_reu = mutant_score - wild_score
    runtime = {
        "python_executable": sys.executable,
        "pyrosetta_file": getattr(pyrosetta, "__file__", None),
        "pyrosetta_version": getattr(pyrosetta, "__version__", None),
        "init_options": init_options,
        "pyrosetta_init_executed": True,
        "added_sys_paths": added_paths,
        "install_path": install_path,
    }
    ddg_table = {
        "backend": "pyrosetta",
        "protocol": "minimal_scorefxn_single_mutation_smoke",
        "ddg_units": "REU",
        "negative_ddg_is_stabilizing": True,
        "runtime_smoke_only_not_training_label": True,
        "rows": [
            {
                "structure_id": structure.get("structure_id"),
                "chain_id": chain_id,
                "pdb_position": position,
                "wild_type": observed_wt,
                "mutant": mutant,
                "mutation": f"{observed_wt}{position}{mutant}",
                "pose_index": pose_index,
                "wild_score_reu": wild_score,
                "mutant_score_reu": mutant_score,
                "ddg_reu": ddg_reu,
                "manual_review_required": True,
                "training_label": False,
            }
        ],
    }
    runtime_log = {
        "status": "completed",
        "command": [sys.executable, "scripts/build_pyrosetta_physical_smoke_bootstrap.py"],
        "pyrosetta_init_executed": True,
        "ddg_protocol_executed": True,
        "stdout_head": "",
        "stderr_head": "",
    }
    return runtime, ddg_table, runtime_log


def build_markdown(report: dict[str, Any]) -> str:
    row = ((report.get("ddg_table") or {}).get("rows") or [{}])[0]
    return "\n".join([
        "# PyRosetta Physical Smoke Bootstrap",
        "",
        f"Created: `{report['created_at']}`",
        "",
        "| Check | Value |",
        "| --- | --- |",
        f"| License local evaluation approved | {report['license_local_evaluation_approved']} |",
        f"| Backend config enabled | {report['backend_config_enabled']} |",
        f"| PyRosetta init executed | {report['pyrosetta_init_executed']} |",
        f"| ddG smoke executed | {report['ddg_protocol_executed']} |",
        f"| Smoke passed | {report['physical_smoke_passed']} |",
        f"| Mutation | {row.get('mutation')} |",
        f"| ddG REU | {row.get('ddg_reu')} |",
        f"| Artifact count | {len(report.get('smoke_artifact_sha256') or {})} |",
        "",
        "Boundary: runtime smoke only; not a wet-lab label, not training-import eligible, not model-claim ready, not release-ready.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PyRosetta bootstrap physical smoke artifacts")
    parser.add_argument("--structure-id", default="10MH")
    parser.add_argument("--chain-id", default="A")
    parser.add_argument("--position", type=int, default=10)
    parser.add_argument("--wild-type", default="T")
    parser.add_argument("--mutant", default="A")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-dir", type=Path, default=SMOKE_DIR)
    parser.add_argument("--output-report", type=Path, default=OUT_REPORT)
    parser.add_argument("--output-md", type=Path, default=OUT_MD)
    args = parser.parse_args()

    created_at = datetime.now(timezone.utc).isoformat()
    config = load_json(args.config)
    license_report = load_json(LICENSE_REPORT)
    install_probe = load_json(INSTALL_PROBE)
    structure = find_structure(args.structure_id)
    if str(structure.get("selected_chain_id")) != args.chain_id:
        raise RuntimeError(f"selected chain mismatch for {args.structure_id}: {structure.get('selected_chain_id')} != {args.chain_id}")
    license_ok = license_local_eval_approved(license_report)
    backend_enabled = bool(((config.get("backends") or {}).get("pyrosetta") or {}).get("enabled"))
    if not license_ok:
        raise RuntimeError("PyRosetta local evaluation license decision is not approved")
    if not backend_enabled:
        raise RuntimeError("PyRosetta backend config is not enabled")
    if ((install_probe.get("import_probe") or {}).get("succeeded")) is not True:
        raise RuntimeError("PyRosetta import probe is not successful")

    mutation = {
        "mutation": f"{args.wild_type}{args.position}{args.mutant}",
        "mutation_position": args.position,
        "wild_type": args.wild_type,
        "mutant": args.mutant,
        "chain_id": args.chain_id,
        "scope": "runtime_smoke_only_not_training_label",
    }
    try:
        runtime, ddg_table, runtime_log = run_pyrosetta_smoke(structure, mutation, config)
        artifacts = write_artifacts(args.output_dir, structure, mutation, runtime, ddg_table, runtime_log)
        status = "completed"
        error = None
    except Exception as exc:
        artifacts = {}
        runtime = {"pyrosetta_init_executed": False}
        ddg_table = {"backend": "pyrosetta", "rows": []}
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        (args.output_dir / "runtime.log").parent.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "runtime.log").write_text(traceback.format_exc(), encoding="utf-8")

    report = {
        "created_at": created_at,
        "local_only": True,
        "backend": "pyrosetta",
        "status": status,
        "error": error,
        "config": str(args.config),
        "license_report": str(LICENSE_REPORT),
        "install_probe": str(INSTALL_PROBE),
        "license_local_evaluation_approved": license_ok,
        "backend_config_enabled": backend_enabled,
        "structure": {
            "structure_id": structure.get("structure_id"),
            "structure_path": structure.get("actual_cache_path"),
            "structure_sha256": structure.get("sha256"),
            "chain_id": structure.get("selected_chain_id"),
            "sequence_to_structure_mapping_status": structure.get("sequence_to_structure_mapping_status"),
        },
        "mutation": mutation,
        "runtime": runtime,
        "pyrosetta_init_executed": runtime.get("pyrosetta_init_executed") is True,
        "ddg_protocol_executed": status == "completed",
        "physical_smoke_passed": status == "completed" and len(artifacts) == len(REQUIRED_ARTIFACTS),
        "required_artifacts": REQUIRED_ARTIFACTS,
        "smoke_output_dir": rel(args.output_dir),
        "smoke_artifact_paths": sorted(artifacts),
        "smoke_artifact_sha256": artifacts,
        "ddg_table": ddg_table,
        "safe_for_training_import": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "PyRosetta runtime smoke is computational physics evidence only. It is not a wet-lab label, not training-import eligible, not model-claim ready, and not release-ready.",
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps({
        "status": status,
        "pyrosetta_init_executed": report["pyrosetta_init_executed"],
        "ddg_protocol_executed": report["ddg_protocol_executed"],
        "physical_smoke_passed": report["physical_smoke_passed"],
        "artifact_count": len(artifacts),
        "output": str(args.output_report),
    }, ensure_ascii=False))
    return 0 if report["physical_smoke_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
