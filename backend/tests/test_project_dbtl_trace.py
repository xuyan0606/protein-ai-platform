"""DBTL trace envelope and project ACL tests."""

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.conversation import Conversation
from app.models.experiment_feedback import ExperimentFeedbackRecord
from app.models.project import Project, ProjectMember
from app.models.strategy_checkpoint import StrategyCheckpoint, WetLabCalibrationRun
from app.models.user import User


async def _create_user(session, email: str) -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name=email.split("@")[0],
    )
    session.add(user)
    await session.flush()
    return user


def _login(client, user: User) -> None:
    client.cookies.clear()
    client.cookies.set("pa_token", create_access_token(user.id))


async def _seed_trace(session, owner: User) -> tuple[Project, int]:
    project = Project(name="DBTL trace project", description="trace", user_id=owner.id)
    session.add(project)
    await session.flush()

    conversation = Conversation(user_id=owner.id, project_id=project.id, title="DBTL round one")
    session.add(conversation)
    await session.flush()

    checkpoint = StrategyCheckpoint(
        user_id=owner.id,
        conversation_id=conversation.id,
        project_id=project.id,
        task_text="design A10V",
        task_fingerprint="task-r1",
        strategy_signature="signature-r1",
        revision=1,
        status="completed",
        plan_payload=[
            {
                "metadata": {
                    "round_key": "R1",
                    "variant_key": "A10V",
                    "prediction": {"activity": "watch", "stability": "go"},
                }
            }
        ],
        evidence_state={},
        artifacts={},
        policy_payload={
            "metadata": {
                "formal_decision": {
                    "decision": "watch",
                    "basis": ["prediction"],
                }
            }
        },
    )
    session.add(checkpoint)
    await session.flush()

    feedback = ExperimentFeedbackRecord(
        created_by_user_id=owner.id,
        project_id=project.id,
        variant_name="A10V",
        parent_variant="WT",
        mutations=["A10V"],
        assay_payload={"metadata": {"round_key": "R1"}},
        metrics_payload={},
        quality_payload={},
        interpretation_payload={"decision": "go", "wt_baseline_status": "ready"},
    )
    session.add(feedback)
    await session.flush()

    session.add(
        ExperimentFeedbackRecord(
            created_by_user_id=owner.id,
            project_id=project.id,
            variant_name="B20G",
            parent_variant="WT",
            mutations=["B20G"],
            assay_payload={"metadata": {"round_key": "R2"}},
            metrics_payload={},
            quality_payload={},
            interpretation_payload={"decision": "watch"},
        )
    )
    session.add(
        WetLabCalibrationRun(
            user_id=owner.id,
            project_id=project.id,
            objective="multi_objective",
            assay_key="activity|substrate|7|25",
            dataset_fingerprint="trace-r1",
            feedback_record_ids=[feedback.id],
            measured_variant_count=1,
            go_count=1,
            watch_count=0,
            no_go_count=0,
            hit_rate=1.0,
            data_quality_grade="insufficient_small_n",
            evidence_level="computational_hypothesis_with_feedback",
            calibration_payload={"round_key": "R1", "wt_baseline_status": "ready"},
        )
    )
    await session.commit()
    return project, checkpoint.id


async def test_dbtl_trace_envelope_is_read_only_and_filters_round(client, session):
    owner = await _create_user(session, "dbtl-owner@example.com")
    project, _ = await _seed_trace(session, owner)
    _login(client, owner)

    response = await client.get(f"/api/projects/{project.id}/dbtl/trace")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dbtl_trace_v1"
    assert payload["project_id"] == project.id
    assert payload["round_key"] == "unknown"
    assert payload["project_model"]["schema_version"] == "dbtl_project_model_v1"
    assert payload["project_model"]["status"] == "partial"
    assert payload["project_model"]["read_only"] is True
    assert payload["project_model"]["counts"]["rounds"] == 2
    assert payload["project_model"]["counts"]["variants"] == 2
    assert payload["project_model"]["counts"]["predictions"] == 1
    assert payload["project_model"]["entities"]["formal_decision"]["decision"] == "watch"
    assert "formal_decision" not in payload["project_model"]["missing_entities"]
    assert payload["learning_readiness"]["schema_version"] == "dbtl_learning_readiness_v1"
    assert payload["learning_readiness"]["status"] == "feedback_present_not_training_ready"
    assert payload["learning_readiness"]["training_eligible_count"] == 0
    assert payload["learning_readiness"]["missing_for_training_counts"]["qc_status_passed"] == 2
    assert payload["next_round_library_design"]["schema_version"] == "next_round_library_design_v1"
    assert payload["next_round_library_design"]["status"] == "blocked_no_validated_singletons"
    assert payload["trace_summary"]["schema_version"] == "dbtl_trace_summary_v1"
    assert payload["trace_summary"]["status"] == "partial_action_required"
    bridge = payload["trace_summary"]["readiness_bridge"]
    assert bridge["schema_version"] == "dbtl_readiness_bridge_v1"
    assert bridge["status"] == "partial"
    assert bridge["read_only"] is True
    assert bridge["project_memory_readiness_status"] == "ready"
    assert bridge["feedback_readiness_status"] == "feedback_present_not_training_ready"
    assert bridge["next_round_constraint_status"] == "blocked_by_feedback_import_contract"
    assert bridge["combination_evidence_status"] == "not_applicable_no_pair_candidates"
    assert "complete_feedback_import_contract" in bridge["required_actions"]
    assert "validate_single_mutants_before_combination" in bridge["required_actions"]
    assert bridge["must_not_claim"][0] == "formal_dbtl_tables_exist"
    memory_readiness = payload["trace_summary"]["project_memory_readiness"]
    assert memory_readiness["schema_version"] == "dbtl_project_memory_readiness_v1"
    assert memory_readiness["status"] == "ready"
    assert memory_readiness["read_only"] is True
    assert memory_readiness["ready_entity_count"] == 6
    assert memory_readiness["missing_entity_count"] == 0
    assert memory_readiness["entity_status"]["round"]["status"] == "ready"
    assert memory_readiness["entity_status"]["ready_wt_baseline"]["status"] == "ready"
    assert "formal_dbtl_tables_exist" in memory_readiness["must_not_claim"]
    feedback_readiness = payload["trace_summary"]["feedback_readiness"]
    assert feedback_readiness["schema_version"] == "dbtl_feedback_readiness_summary_v1"
    assert feedback_readiness["status"] == "feedback_present_not_training_ready"
    assert feedback_readiness["read_only"] is True
    assert feedback_readiness["record_count"] == 2
    assert feedback_readiness["training_eligible_count"] == 0
    assert feedback_readiness["training_batch_minimum"] == 12
    assert feedback_readiness["missing_for_training_counts"]["qc_status_passed"] == 2
    assert feedback_readiness["assay_qc_summary"]["qc_status_counts"]["missing"] == 2
    assert feedback_readiness["assay_qc_summary"]["replicate_counts"]["missing_or_insufficient"] == 2
    assert feedback_readiness["next_round_constraint_status"] == "blocked_by_feedback_import_contract"
    assert "model_trained" in feedback_readiness["must_not_claim"]
    assert "wet_lab_validated_by_trace_summary" in feedback_readiness["must_not_claim"]
    assert payload["trace_summary"]["learning_status"] == "feedback_present_not_training_ready"
    assert payload["trace_summary"]["next_round_status"] == "blocked_no_validated_singletons"
    assert payload["trace_summary"]["next_round_structural_distance_source"] == "none"
    assert payload["trace_summary"]["next_round_combination_evidence_status"] == "not_applicable_no_pair_candidates"
    assert payload["trace_summary"]["counts"]["feedback_records"] == 2
    assert {
        item["reason"]: item["count"]
        for item in payload["trace_summary"]["top_missing_for_training"]
    }["qc_status_passed"] == 2
    assert {
        item["action"]
        for item in payload["trace_summary"]["required_actions"]
    } >= {
        "complete_feedback_import_contract",
        "validate_single_mutants_before_combination",
    }
    required_actions = {
        item["action"]: item
        for item in payload["trace_summary"]["required_actions"]
    }
    assert required_actions["complete_feedback_import_contract"]["category"] == "assay_qc"
    assert required_actions["complete_feedback_import_contract"]["priority"] == "P0"
    assert required_actions["validate_single_mutants_before_combination"]["category"] == "combination_gate"
    assert payload["trace_summary"]["required_action_contract"]["schema_version"] == "dbtl_required_action_contract_v1"
    assert payload["trace_summary"]["required_action_contract"]["status"] == "action_required"
    assert payload["trace_summary"]["required_action_contract"]["by_category"]["assay_qc"] >= 1
    assert payload["trace_summary"]["required_action_contract"]["by_priority"]["P0"] >= 1
    assert payload["trace_summary"]["required_action_contract"]["read_only"] is True
    p4 = payload["trace_summary"]["p4_closed_loop_readiness"]
    assert p4["schema_version"] == "p4_closed_loop_readiness_v1"
    assert p4["status"] == "blocked"
    assert p4["read_only"] is True
    assert p4["gates"]["active_learning_batch"]["status"] == "blocked"
    assert p4["gates"]["model_calibration_registry"]["status"] == "ready"
    assert p4["gates"]["live_gate_approval"]["status"] == "blocked"
    operator_review = p4["operator_review_contract"]
    assert operator_review["schema_version"] == "p4_operator_review_contract_v1"
    assert operator_review["status"] == "blocked_missing_operator_review"
    assert operator_review["read_only"] is True
    assert "operator_review_not_recorded" in operator_review["blocked_reasons"]
    assert "live_gate_approval_not_ready" in operator_review["blocked_reasons"]
    assert "live_gate_approved" in operator_review["must_not_claim"]
    active_learning = p4["active_learning_batch_contract"]
    assert active_learning["schema_version"] == "p4_active_learning_batch_contract_v1"
    assert active_learning["status"] == "blocked_insufficient_training_feedback"
    assert active_learning["read_only"] is True
    assert active_learning["observed"]["training_eligible_count"] == 0
    assert "active_learning_batch_executed" in active_learning["must_not_claim"]
    calibration_registry = p4["model_calibration_registry_contract"]
    assert calibration_registry["schema_version"] == "p4_model_calibration_registry_contract_v1"
    assert calibration_registry["status"] == "ready_read_only_registry"
    assert calibration_registry["observed"]["calibration_runs"] == 1
    assert "model_retrained" in calibration_registry["must_not_claim"]
    manufacturing_contract = p4["manufacturing_constraint_contract"]
    assert manufacturing_contract["schema_version"] == "p4_manufacturing_constraint_schema_v1"
    assert manufacturing_contract["status"] == "blocked_missing_process_constraints"
    assert "manufacturing_constraints_not_ready" in manufacturing_contract["blocked_reasons"]
    assert "model_retrained" in p4["must_not_claim"]
    assert "manufacturing_constraints_validated" in p4["must_not_claim"]
    assert payload["trace_summary"]["report_contract"]["must_not_claim_training_or_wet_lab_validation"] is True
    assert payload["wt_baseline"]["status"] == "ready"
    assert payload["wt_baseline"]["calibration_runs"][0]["id"] > 0
    assert payload["formal_decision"]["decision"] == "watch"
    assert payload["variants"][0]["variant_key"] == "A10V"
    assert payload["variants"][0]["prediction"] == {
        "activity": "watch",
        "stability": "go",
    }
    assert payload["variants"][0]["decision"] == "unknown"

    filtered = await client.get(
        f"/api/projects/{project.id}/dbtl/trace",
        params={"round_key": "R1"},
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["round_key"] == "R1"
    assert [item["variant_key"] for item in filtered_payload["variants"]] == ["A10V"]
    assert filtered_payload["wt_baseline"]["feedback_record_ids"] == []

    missing_round = await client.get(
        f"/api/projects/{project.id}/dbtl/trace",
        params={"round_key": "R9"},
    )
    assert missing_round.status_code == 200
    assert missing_round.json()["variants"] == []
    assert missing_round.json()["wt_baseline"]["status"] == "unknown"
    assert missing_round.json()["project_model"]["status"] == "empty"
    assert missing_round.json()["learning_readiness"]["status"] == "missing_feedback"
    assert missing_round.json()["next_round_library_design"] == {}
    assert missing_round.json()["trace_summary"]["status"] == "missing_project_memory"
    missing_memory = missing_round.json()["trace_summary"]["project_memory_readiness"]
    assert missing_memory["schema_version"] == "dbtl_project_memory_readiness_v1"
    assert missing_memory["status"] == "empty"
    assert missing_memory["missing_entity_count"] == 6
    assert "round" in missing_memory["missing_entities"]
    assert missing_memory["entity_status"]["experiment_feedback"]["status"] == "missing"
    missing_feedback_readiness = missing_round.json()["trace_summary"]["feedback_readiness"]
    assert missing_feedback_readiness["schema_version"] == "dbtl_feedback_readiness_summary_v1"
    assert missing_feedback_readiness["status"] == "missing_feedback"
    assert missing_feedback_readiness["record_count"] == 0
    assert missing_feedback_readiness["read_only"] is True
    assert missing_round.json()["trace_summary"]["next_round_status"] == "unknown"
    assert missing_round.json()["trace_summary"]["next_round_combination_evidence_status"] == "unknown"
    assert "create_or_select_round" in {
        item["action"]
        for item in missing_round.json()["trace_summary"]["required_actions"]
    }
    assert "round" in missing_round.json()["project_model"]["missing_entities"]


async def test_dbtl_trace_viewer_can_read_but_non_member_cannot(client, session):
    owner = await _create_user(session, "dbtl-acl-owner@example.com")
    viewer = await _create_user(session, "dbtl-acl-viewer@example.com")
    outsider = await _create_user(session, "dbtl-acl-outsider@example.com")
    project, _ = await _seed_trace(session, owner)
    session.add(ProjectMember(project_id=project.id, user_id=viewer.id, role="viewer"))
    await session.commit()

    _login(client, viewer)
    viewer_response = await client.get(f"/api/projects/{project.id}/dbtl/trace")
    assert viewer_response.status_code == 200
    assert viewer_response.json()["project_id"] == project.id

    _login(client, outsider)
    outsider_response = await client.get(f"/api/projects/{project.id}/dbtl/trace")
    assert outsider_response.status_code == 404
    assert "A10V" not in outsider_response.text


async def test_dbtl_trace_exposes_feedback_to_next_round_constraints(client, session):
    owner = await _create_user(session, "dbtl-next-round-owner@example.com")
    project = Project(name="DBTL next round project", description="feedback loop", user_id=owner.id)
    session.add(project)
    await session.flush()

    for mutation in ("A10V", "D80N"):
        session.add(
            ExperimentFeedbackRecord(
                created_by_user_id=owner.id,
                project_id=project.id,
                variant_name=mutation,
                parent_variant="WT",
                mutations=[mutation],
                assay_payload={
                    "metadata": {"round_key": "R1"},
                    "sample_type": "purified_enzyme",
                    "assay_type": "specific_activity",
                    "substrate": "pNP-C8",
                    "ph": 7.0,
                    "temperature_c": 37,
                    "buffer": "Tris",
                },
                metrics_payload={
                    "specific_activity_fold_vs_wt": 1.3,
                    "activity_retention_pct": 95,
                },
                quality_payload={
                    "qc_status": "passed",
                    "replicate_count": 3,
                    "sec_monomer_pct": 95,
                },
                interpretation_payload={"decision": "go"},
            )
        )
    await session.commit()

    _login(client, owner)
    response = await client.get(f"/api/projects/{project.id}/dbtl/trace")
    assert response.status_code == 200
    payload = response.json()
    library = payload["next_round_library_design"]

    assert payload["trace_summary"]["next_round_status"] == "singletons_only_extend_validation"
    assert payload["trace_summary"]["next_round_structural_distance_source"] == "none"
    assert payload["trace_summary"]["next_round_combination_evidence_status"] == "blocked_or_not_promoted"
    assert library["schema_version"] == "next_round_library_design_v1"
    assert library["status"] == "singletons_only_extend_validation"
    assert library["structural_distance_source"] == "none"
    assert library["combination_evidence_contract"]["schema_version"] == "next_round_combination_evidence_contract_v1"
    assert library["combination_evidence_contract"]["status"] == "blocked_or_not_promoted"
    assert "validated_combination_effect" in library["combination_evidence_contract"]["must_not_claim"]
    assert library["source_evidence"]["validated_single_mutants"] == 2
    assert {item["mutation"] for item in library["single_point_pool"]} == {"A10V", "D80N"}
    assert library["combination_pool"] == []
    assert any(
        group["well_group"] == "validated_singletons"
        and group["variants"] == ["A10V", "D80N"]
        for group in library["plate_layout"]
    )
    assert "matched WT and parent controls in the same plate/batch" in library["assay_required"]
    assert library["higher_order_rule"]["status"] == "blocked"
    assert "direct singleton" in library["boundary"]


async def test_dbtl_trace_deduplicates_wt_and_reports_unresolved_calibration_links(
    client, session
):
    owner = await _create_user(session, "dbtl-quality-owner@example.com")
    project, _ = await _seed_trace(session, owner)
    feedback = (
        await session.execute(
            select(ExperimentFeedbackRecord)
            .where(ExperimentFeedbackRecord.project_id == project.id)
            .order_by(ExperimentFeedbackRecord.id.asc())
        )
    ).scalars().first()
    assert feedback is not None

    duplicate_wt = ExperimentFeedbackRecord(
        created_by_user_id=owner.id,
        project_id=project.id,
        variant_name="WT",
        parent_variant=None,
        mutations=[],
        assay_payload={"metadata": {"round_key": "R1"}},
        metrics_payload={},
        quality_payload={},
        interpretation_payload={"wt_baseline_status": "ready"},
    )
    session.add(duplicate_wt)
    session.add(
        WetLabCalibrationRun(
            user_id=owner.id,
            project_id=project.id,
            objective="quality-link-check",
            assay_key="activity|substrate|7|25",
            dataset_fingerprint="trace-quality",
            feedback_record_ids=[feedback.id, feedback.id, 999999],
            measured_variant_count=1,
            go_count=1,
            watch_count=0,
            no_go_count=0,
            hit_rate=1.0,
            data_quality_grade="insufficient_small_n",
            evidence_level="computational_hypothesis_with_feedback",
            calibration_payload={"round_key": "R1", "wt_baseline_status": "ready"},
        )
    )
    await session.commit()

    _login(client, owner)
    response = await client.get(f"/api/projects/{project.id}/dbtl/trace")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["wt_baseline"]["feedback_record_ids"]) == len(
        set(payload["wt_baseline"]["feedback_record_ids"])
    )
    quality_run = next(
        item
        for item in payload["wt_baseline"]["calibration_runs"]
        if item["dataset_fingerprint"] == "trace-quality"
    )
    assert quality_run["feedback_record_ids"] == [feedback.id]
    assert quality_run["unresolved_feedback_record_ids"] == [999999]


async def test_dbtl_trace_conflicting_formal_decisions_fail_closed(client, session):
    owner = await _create_user(session, "dbtl-conflict-owner@example.com")
    project, checkpoint_id = await _seed_trace(session, owner)
    original = await session.get(StrategyCheckpoint, checkpoint_id)
    assert original is not None
    session.add(
        StrategyCheckpoint(
            user_id=owner.id,
            conversation_id=original.conversation_id,
            project_id=project.id,
            task_text="design A10V follow-up",
            task_fingerprint="task-r1-follow-up",
            strategy_signature="signature-r1-follow-up",
            revision=2,
            status="completed",
            plan_payload=[{"metadata": {"round_key": "R1", "variant_key": "A10V"}}],
            evidence_state={},
            artifacts={},
            policy_payload={
                "metadata": {
                    "formal_decision": {
                        "decision": "go",
                        "basis": ["follow-up"],
                    }
                }
            },
        )
    )
    await session.commit()

    _login(client, owner)
    response = await client.get(f"/api/projects/{project.id}/dbtl/trace")
    assert response.status_code == 200
    formal_decision = response.json()["formal_decision"]
    assert formal_decision["decision"] == "unknown"
    assert formal_decision["status"] == "conflict"
    project_model = response.json()["project_model"]
    assert project_model["entities"]["formal_decision"]["status"] == "conflict"
    assert "formal_decision" in project_model["missing_entities"]
