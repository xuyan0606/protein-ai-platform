import pytest
import json
from pathlib import Path

from app.services.enzyme_workflow_runtime import evaluate_enzyme_workflow_runtime


REGRESSION_CASES = json.loads(
    (Path(__file__).with_name("enzyme_workflow_regression_cases.json")).read_text()
)


@pytest.mark.parametrize("case", REGRESSION_CASES, ids=lambda case: case["id"])
def test_deidentified_conversation_regressions(case):
    result = evaluate_enzyme_workflow_runtime(
        case["message"], history=case["history"], session_id=case["id"]
    )

    for field, expected in case["expected"].items():
        assert result[field] == expected


def test_identity_consistency_blocks_conflicting_labels_for_same_sequence():
    from app.services.identity_consistency import check_identity_consistency, clear_identity_cache

    clear_identity_cache()
    sequence = "MKTIIALSYIFCLVFADYKDDDDK"
    first = check_identity_consistency(sequence, {"identity_label": "aspartic protease"})
    second = check_identity_consistency(sequence, {"identity_label": "lipase"})

    assert first["status"] == "CONSISTENT"
    assert second["status"] == "NEEDS_REVIEW"
    assert second["previous_identity"] == "aspartic protease"


def test_identity_consistency_separates_model_and_evidence_versions():
    from app.services.identity_consistency import check_identity_consistency, clear_identity_cache

    clear_identity_cache()
    sequence = "MKTIIALSYIFCLVFADYKDDDDK"
    check_identity_consistency(
        sequence, {"identity_label": "aspartic protease"}, model_version="m1", evidence_version="e1"
    )
    result = check_identity_consistency(
        sequence, {"identity_label": "lipase"}, model_version="m2", evidence_version="e2"
    )

    assert result["status"] == "CONSISTENT"
    assert result["previous_identity"] is None


def test_plain_question_is_non_execution_with_complete_contract():
    result = evaluate_enzyme_workflow_runtime(
        "热稳定性是什么意思？", history=[], session_id="conv-1"
    )

    assert result["intent"] == "NON_EXECUTION"
    assert result["intake_status"] == "NOT_APPLICABLE"
    assert result["final_status"] == "READY"
    assert result["workflow_id"] is None
    assert result["session_id"] == "conv-1"
    assert result["trace"] == []
    assert result["fallback_trace"] == []


def test_continuation_with_prior_enzyme_task_does_not_start_a_new_task():
    result = evaluate_enzyme_workflow_runtime(
        "继续", history=[{"role": "user", "content": "提高这个酶的热稳定性"}], session_id="conv-2"
    )

    assert result["intent"] == "FOLLOW_UP"
    assert result["intake_status"] == "READY_FOR_ANALYSIS"
    assert result["final_status"] == "READY"


@pytest.mark.parametrize("message", ["继续", "再说人话", "这个什么意思"])
def test_common_followup_phrases_reuse_existing_enzyme_task(message):
    result = evaluate_enzyme_workflow_runtime(
        message,
        history=[
            {"role": "user", "content": "提高这个酶的热稳定性，序列：MKTIIALSYIFCLVFADYKDDDDK"},
            {"role": "assistant", "content": "已识别为热稳定性任务。"},
        ],
        session_id="conv-followup",
    )

    assert result["intent"] == "FOLLOW_UP"
    assert result["workflow_id"] == "WF-STABILITY"
    assert result["route_reason"] == "continuation_of_existing_task"


def test_activity_request_without_sequence_waits_for_user_input():
    result = evaluate_enzyme_workflow_runtime("提高比活力", history=[], session_id="conv-3")

    assert result["intent"] == "NEW_TASK"
    assert result["intake_status"] == "WAITING_FOR_USER_INPUT"
    assert result["final_status"] == "NEEDS_INPUT"
    assert "enzyme_sequence_or_structure_or_accession" in result["input_gaps"]
    assert result["workflow_id"] is None


def test_sequence_update_is_recognized_and_makes_task_ready():
    result = evaluate_enzyme_workflow_runtime(
        "序列：MKTIIALSYIFCLVFADYKDDDDK", 
        history=[{"role": "user", "content": "提高比活力"}],
        session_id="conv-4",
    )

    assert result["intent"] == "INPUT_UPDATE"
    assert result["intake_status"] == "READY_FOR_ANALYSIS"
    assert result["final_status"] == "READY"
    assert "sequence" in result["known_inputs"]


def test_explicit_target_change_is_recognized():
    result = evaluate_enzyme_workflow_runtime(
        "改成提高热稳定性", history=[{"role": "user", "content": "提高比活力，序列：MKTIIALSYIFCLVFADYKDDDDK"}], session_id="conv-5"
    )

    assert result["intent"] == "TARGET_CHANGE"
    assert result["workflow_id"] == "WF-STABILITY"


def test_question_about_model_in_protein_chat_is_non_execution():
    result = evaluate_enzyme_workflow_runtime(
        "这个结果是什么意思？",
        history=[
            {"role": "user", "content": "提高这个酶的热稳定性，序列：MKTIIALSYIFCLVFADYKDDDDK"},
            {"role": "assistant", "content": "这是一个预测结果。"},
        ],
        session_id="conv-question",
    )

    assert result["intent"] == "NON_EXECUTION"
    assert result["workflow_id"] is None
    assert result["input_gaps"] == []
