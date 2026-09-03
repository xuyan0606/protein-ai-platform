import json

from validate_production_model_gate import evaluate


def test_current_project_is_not_production_ready():
    result = evaluate(__import__('pathlib').Path('.'))
    assert result["production_ready"] is False
    assert result["blockers"]
    assert result["evidence"]["strict_supervised_rows"] == 0


def test_gate_requires_all_hard_requirements(tmp_path):
    base = tmp_path; (base / "reports").mkdir()
    for name, payload in {
        "training_readiness_report.json": {"ready_for_supervised_small_model_claim": True, "label_integrity": {"strict_supervised_rows": 100, "claim_eligible_supervised_rows": 100}, "multitask_training": {"ready_head_count": 5}},
        "master_readiness_board.json": {"ready_streams": 8, "overall_status": "ready"},
        "msa_conservation_readiness_report.json": {"ready": True, "missing": 0},
        "structure_chain_mapping_backlog_readiness_report.json": {"remaining_unreviewed_rows": 0},
        "experiment_feedback_readiness_report.json": {"ready_for_training": True},
        "local_release_manifest.json": {"release_ready": True},
        "p31_production_execution_gap_audit_report.json": {"production_execution_allowed": True, "deploy_allowed": True},
        "production_model_package_validation_report.json": {"production_model_artifact": True},
        "production_training_run.json": {"status": "completed", "training_executed": True},
    }.items():
        (base / "reports" / name).write_text(json.dumps(payload))
    result = evaluate(base)
    assert result["production_ready"] is True
