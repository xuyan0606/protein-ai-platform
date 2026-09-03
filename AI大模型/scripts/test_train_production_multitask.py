import json
from pathlib import Path

from train_production_multitask import run_training


def test_training_is_blocked_when_gate_is_not_ready(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "production_model_gate.json").write_text(json.dumps({"production_ready": False, "blockers": ["labels"]}))
    result = run_training(tmp_path)
    assert result["status"] == "blocked_pending_production_gate"
    assert result["training_executed"] is False
    assert result["safe_for_model_claim"] is False
    assert result["release_ready"] is False
    assert (reports / "production_training_run.json").exists()


def test_training_requires_execution_contract_when_gate_is_true(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "production_model_gate.json").write_text(json.dumps({"production_ready": True, "blockers": []}))
    result = run_training(tmp_path)
    assert result["status"] == "blocked_pending_training_execution_contract"
    assert result["training_executed"] is False


def test_training_blocks_when_dataset_is_missing(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "production_model_gate.json").write_text(json.dumps({"production_ready": True, "blockers": []}))
    (reports / "five_head_training_execution_contract_report.json").write_text(
        json.dumps({"training_execution_allowed": True, "ready_head_count": 5})
    )
    result = run_training(tmp_path)
    assert result["status"] == "blocked_missing_training_dataset"
    assert result["training_executed"] is False
    assert "five_head_training_labels.jsonl" in result["blockers"][0]


def test_every_blocked_receipt_is_non_claim_and_non_release(tmp_path):
    result = run_training(tmp_path)
    assert result["training_executed"] is False
    assert result["safe_for_model_claim"] is False
    assert result["release_ready"] is False


def test_training_blocks_when_dataset_manifest_is_missing(tmp_path):
    reports = tmp_path / "reports"
    dataset_dir = tmp_path / "datasets" / "training"
    reports.mkdir()
    dataset_dir.mkdir(parents=True)
    (reports / "production_model_gate.json").write_text(
        json.dumps({"production_ready": True, "blockers": []})
    )
    (reports / "five_head_training_execution_contract_report.json").write_text(
        json.dumps({"training_execution_allowed": True, "ready_head_count": 5})
    )
    (dataset_dir / "five_head_training_labels.jsonl").write_text(
        json.dumps({"head": "activity_risk", "label_value": "low"}) + "\n"
    )

    result = run_training(tmp_path)

    assert result["status"] == "blocked_missing_or_invalid_training_input_manifest"
    assert result["training_executed"] is False


def test_completed_training_receipt_does_not_authorize_claim_or_release(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    dataset_dir = tmp_path / "datasets" / "training"
    reports.mkdir()
    dataset_dir.mkdir(parents=True)
    (reports / "production_model_gate.json").write_text(
        json.dumps({"production_ready": True, "blockers": [], "evidence": {"release_ready": True}})
    )
    (reports / "five_head_training_execution_contract_report.json").write_text(
        json.dumps({"training_execution_allowed": True, "ready_head_count": 5})
    )
    dataset = dataset_dir / "five_head_training_labels.jsonl"
    dataset.write_text(
        json.dumps({"head": "activity_risk", "label_value": "low"}) + "\n"
    )
    import hashlib

    (reports / "five_head_training_input_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "kwb_five_head_training_input_manifest_v1",
                "ready_for_training_execution": True,
                "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
            }
        )
    )
    monkeypatch.setattr(
        "train_production_multitask.run_training_core",
        lambda *args, **kwargs: {
            "training_executed": True,
            "trained_heads": [
                "mutation_rank",
                "stability",
                "activity_risk",
                "substrate_fit",
                "assay_success",
            ],
            "checkpoint_path": "checkpoint.pt",
        },
    )

    result = run_training(tmp_path)

    assert result["status"] == "completed_production_training"
    assert result["safe_for_model_claim"] is False
    assert result["release_ready"] is False
