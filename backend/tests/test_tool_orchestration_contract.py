from app.services.tool_orchestration_contract import evidence_from_completed_tasks, is_terminal_tool_evidence, validate_tool_plan
from app.services.scheduler import ASYNC_TOOLS, get_task_profile
from app.tools.registry import ToolRegistry


def test_plan_blocks_structure_and_sequence_tools_without_inputs():
    result = validate_tool_plan([
        {"tool_name": "enzyme_identity_profile"},
        {"tool_name": "gromacs_md"},
    ])

    assert result["allowed"] is False
    assert {item["code"] for item in result["violations"]} == {
        "sequence_required", "structure_required",
    }


def test_plan_blocks_candidates_until_identity_and_objective_gates():
    result = validate_tool_plan(
        [{"tool_name": "mutation_priority_score"}],
        evidence={"has_sequence": True},
    )

    assert result["allowed"] is False
    assert {item["code"] for item in result["violations"]} == {
        "identity_gate_required", "objective_gate_required",
    }


def test_plan_allows_valid_foundation_and_candidate_chain():
    result = validate_tool_plan(
        [
            {"tool_name": "enzyme_identity_profile"},
            {"tool_name": "enzyme_objective_module_plan"},
            {"tool_name": "mutation_priority_score"},
        ],
        evidence={
            "has_sequence": True,
            "identity_ready": True,
            "objective_ready": True,
        },
    )

    assert result["allowed"] is True
    assert result["violations"] == []


def test_plan_reports_missing_tool_name_fail_closed():
    result = validate_tool_plan([{}])
    assert result["allowed"] is False
    assert result["violations"] == [{"index": 0, "code": "missing_tool_name"}]


def test_plan_confirmation_defers_candidate_evidence_gates_to_ordered_execution():
    result = validate_tool_plan(
        [{"tool_name": "mutation_priority_score"}],
        evidence={"has_sequence": True},
        enforce_candidate_gates=False,
    )
    assert result["allowed"] is True


def test_plan_blocks_async_tool_sync_override():
    result = validate_tool_plan([
        {"tool_name": "blast_search", "params": {"allow_interactive_sync_run": True}},
    ], evidence={"has_sequence": True})
    assert result["allowed"] is False
    assert result["violations"] == [{
        "index": 0, "tool": "blast_search", "code": "async_tool_sync_override",
    }]


def test_plan_blocks_unknown_tool():
    result = validate_tool_plan([{"tool_name": "not_registered"}])
    assert result["allowed"] is False
    assert result["violations"][0]["code"] == "unknown_tool"


def test_async_registry_timeouts_fit_scheduler_hard_limits():
    ToolRegistry.discover()
    mismatches = []
    for name in ASYNC_TOOLS:
        tool = ToolRegistry.get_tool(name)
        profile = get_task_profile(name)
        if tool and tool.timeout_seconds > profile.time_limit:
            mismatches.append((name, tool.timeout_seconds, profile.time_limit))
    assert mismatches == []


def test_dependency_order_blocks_candidate_before_identity_and_objective():
    result = validate_tool_plan(
        [{"tool_name": "mutation_priority_score"}],
        evidence={"has_sequence": True, "numbering_ready": True},
        enforce_dependency_order=True,
    )
    assert result["allowed"] is False
    assert {item["dependency"] for item in result["violations"] if item["code"] == "dependency_required"} == {
        "identity_profile", "objective_module",
    }


def test_dependency_order_accepts_identity_objective_then_candidate():
    result = validate_tool_plan(
        [
            {"tool_name": "enzyme_identity_profile"},
            {"tool_name": "enzyme_objective_module_plan"},
            {"tool_name": "mutation_priority_score"},
        ],
        evidence={"has_sequence": True, "numbering_ready": True},
        enforce_dependency_order=True,
    )
    assert result["allowed"] is True


def test_dependency_order_blocks_docking_without_structure_and_ligand():
    result = validate_tool_plan(
        [{"tool_name": "diffdock_docking"}],
        enforce_dependency_order=True,
    )
    assert result["allowed"] is False
    assert {item["dependency"] for item in result["violations"] if item["code"] == "dependency_required"} == {
        "structure", "ligand_3d",
    }


def test_dependency_order_blocks_numbering_before_sifts_mapping():
    result = validate_tool_plan([{"tool_name": "residue_numbering_gate"}], evidence={"has_structure": True}, enforce_dependency_order=True)
    assert result["allowed"] is False
    assert {item["dependency"] for item in result["violations"] if item["code"] == "dependency_required"} == {"residue_mapping"}


def test_dependency_order_accepts_sifts_mapping_before_numbering():
    result = validate_tool_plan(
        [{"tool_name": "residue_mapping_sifts"}, {"tool_name": "residue_numbering_gate"}],
        evidence={"has_structure": True}, enforce_dependency_order=True,
    )
    assert result["allowed"] is True


def test_dependency_order_blocks_gromacs_without_topology():
    result = validate_tool_plan([{"tool_name": "gromacs_md"}], evidence={"has_structure": True}, enforce_dependency_order=True)
    assert result["allowed"] is False
    assert {item["dependency"] for item in result["violations"] if item["code"] == "dependency_required"} == {"topology"}


def test_dependency_order_blocks_epistasis_without_candidate_set():
    result = validate_tool_plan([{"tool_name": "mutation_epistasis_check"}], enforce_dependency_order=True)
    assert result["allowed"] is False
    assert {item["dependency"] for item in result["violations"] if item["code"] == "dependency_required"} == {"candidate_set"}


def test_submitted_async_receipt_is_not_terminal_evidence():
    assert is_terminal_tool_evidence("diffdock_docking", {"status": "submitted", "task_id": "t1"}) is False
    assert is_terminal_tool_evidence("diffdock_docking", {"status": "pending", "task_id": "t1"}) is False
    assert is_terminal_tool_evidence("diffdock_docking", {"status": "completed", "result": {"poses": []}}) is True


def test_completed_task_audits_only_unlock_conservative_providers():
    evidence = evidence_from_completed_tasks([
        {"tool_name": "enzyme_identity_profile", "status": "completed"},
        {"tool_name": "ligand_preprocess", "status": "submitted"},
        {"tool_name": "residue_mapping_sifts", "status": "completed"},
    ])
    assert evidence == {"identity_ready": True, "has_residue_mapping": True}
