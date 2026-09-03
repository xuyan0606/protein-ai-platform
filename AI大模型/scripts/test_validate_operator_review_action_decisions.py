import validate_operator_review_action_decisions as validator


def decision(status="completed", evidence=None, reports=None):
    return {
        "action_id": "review_action_001",
        "stream": "external_data_sources",
        "action_status": status,
        "reviewer": "human-operator",
        "reviewed_at": "2026-08-11T00:00:00Z",
        "evidence_artifacts": evidence or [],
        "validation_reports": reports or [],
        "completion_note": "reviewed",
        "residual_risks": [],
    }


def queue_row():
    return {
        "action_id": "review_action_001",
        "stream": "external_data_sources",
        "required_evidence_artifacts": ["required-decision.jsonl"],
        "required_validation_reports": ["required-validation.json"],
    }


def test_needs_more_info_is_decided_but_not_completed():
    decided, completed = validator.action_decision_sets([
        {"action_id": "review_action_001", "valid": True, "completed": False},
    ])
    assert decided == ["review_action_001"]
    assert completed == []


def test_completed_action_rejects_unrelated_existing_evidence(tmp_path, monkeypatch):
    (tmp_path / "unrelated.jsonl").write_text("\n", encoding="utf-8")
    (tmp_path / "unrelated.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(validator, "AI_ROOT", tmp_path)
    row = decision(evidence=["unrelated.jsonl"], reports=["unrelated.json"])
    errors = validator.validate(row, {"review_action_001": queue_row()})
    assert "completed_missing_required_evidence_artifacts" in errors
    assert "completed_missing_required_validation_reports" in errors


def test_completed_action_accepts_bound_required_paths(tmp_path, monkeypatch):
    (tmp_path / "required-decision.jsonl").write_text("\n", encoding="utf-8")
    (tmp_path / "required-validation.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(validator, "AI_ROOT", tmp_path)
    row = decision(evidence=["required-decision.jsonl"], reports=["required-validation.json"])
    assert validator.validate(row, {"review_action_001": queue_row()}) == []


def test_completed_action_rejects_malformed_path_values_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(validator, "AI_ROOT", tmp_path)
    row = decision(evidence=[{"path": "required-decision.jsonl"}], reports=[""])
    errors = validator.validate(row, {"review_action_001": queue_row()})
    assert "missing_evidence_artifacts_paths" in errors
    assert "missing_validation_reports_paths" in errors
    assert "completed_missing_required_evidence_artifacts" in errors
    assert "completed_missing_required_validation_reports" in errors


def test_completed_action_rejects_queue_without_required_path_contract(tmp_path, monkeypatch):
    (tmp_path / "evidence.jsonl").write_text("\n", encoding="utf-8")
    (tmp_path / "validation.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(validator, "AI_ROOT", tmp_path)
    row = decision(evidence=["evidence.jsonl"], reports=["validation.json"])
    queue = queue_row() | {"required_evidence_artifacts": [], "required_validation_reports": []}
    errors = validator.validate(row, {"review_action_001": queue})
    assert "completed_queue_missing_required_evidence_contract" in errors
    assert "completed_queue_missing_required_validation_contract" in errors
