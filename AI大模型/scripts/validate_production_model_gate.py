"""Single fail-closed gate for production enzyme-model readiness."""

import argparse
import json
from pathlib import Path


def _load(base: Path, name: str):
    path = base / "reports" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def evaluate(base: Path):
    training = _load(base, "training_readiness_report.json")
    master = _load(base, "master_readiness_board.json")
    msa = _load(base, "msa_conservation_readiness_report.json")
    chain = _load(base, "structure_chain_mapping_backlog_readiness_report.json")
    feedback = _load(base, "experiment_feedback_readiness_report.json")
    release = _load(base, "local_release_manifest.json")
    production = _load(base, "p31_production_execution_gap_audit_report.json")
    package = _load(base, "production_model_package_validation_report.json")
    training_run = _load(base, "production_training_run.json")
    integrity = training.get("label_integrity", {})
    multitask = training.get("multitask_training", {})
    msa_state = training.get("feature_streams", {}).get("msa_conservation", {})
    evidence = {
        "strict_supervised_rows": integrity.get("strict_supervised_rows", 0),
        "claim_eligible_supervised_rows": integrity.get("claim_eligible_supervised_rows", 0),
        "ready_head_count": multitask.get("ready_head_count", 0),
        "master_ready_streams": master.get("ready_streams", 0),
        "msa_ready": msa_state.get("ready", msa.get("ready", False)),
        "msa_missing": msa_state.get("missing", msa.get("missing")),
        "chain_remaining_unreviewed_rows": chain.get("remaining_unreviewed_rows"),
        "feedback_ready_for_training": feedback.get("ready_for_training", False),
        "release_ready": release.get("release_ready", False),
        "production_execution_allowed": production.get("production_execution_allowed", False),
        "deploy_allowed": production.get("deploy_allowed", False),
        "production_model_artifact": package.get("production_model_artifact", False),
        "production_training_executed": training_run.get("status") == "completed" and training_run.get("training_executed") is True,
    }
    blockers = []
    if evidence["strict_supervised_rows"] < 100 or evidence["claim_eligible_supervised_rows"] < 100:
        blockers.append("requires >=100 strict and claim-eligible real supervised rows")
    if evidence["ready_head_count"] < 5:
        blockers.append("requires all five model heads ready")
    if evidence["master_ready_streams"] < 8:
        blockers.append("master readiness board is not fully ready")
    if not evidence["msa_ready"] or evidence["msa_missing"]:
        blockers.append("MSA conservation feature gate is incomplete")
    if evidence["chain_remaining_unreviewed_rows"]:
        blockers.append("structure chain review remains incomplete")
    if not evidence["feedback_ready_for_training"]:
        blockers.append("wet-lab feedback is not training-authorized")
    if not training.get("ready_for_supervised_small_model_claim", False):
        blockers.append("training readiness does not permit a model-quality claim")
    if not evidence["production_model_artifact"]:
        blockers.append("hash-verified production model package is missing or invalid")
    if not evidence["production_training_executed"]:
        blockers.append("completed production multi-task training receipt is missing")
    if not evidence["release_ready"]:
        blockers.append("release manifest is not release-ready")
    if not evidence["production_execution_allowed"] or not evidence["deploy_allowed"]:
        blockers.append("production execution/deployment is not authorized")
    return {"production_ready": not blockers, "blockers": blockers, "evidence": evidence, "policy": "all production gates are conjunctive; missing evidence blocks release"}


def main():
    p = argparse.ArgumentParser(); p.add_argument("--base", type=Path, required=True); p.add_argument("--output", type=Path, required=True); a = p.parse_args()
    result = evaluate(a.base); a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(json.dumps(result, ensure_ascii=False)); return 0 if result["production_ready"] else 2


if __name__ == "__main__": raise SystemExit(main())
