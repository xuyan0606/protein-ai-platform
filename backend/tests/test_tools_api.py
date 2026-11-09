"""Regression tests for tool task API ownership checks."""

import io
import zipfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import app.tools.gromacs_md  # noqa: F401 - ensure gromacs_md is registered for submit tests
import app.tools.enzyme_function  # noqa: F401 - ensure enzyme_function is registered
import app.tools.enzyme_identity_profile  # noqa: F401 - ensure identity profile is registered
import app.tools.enzyme_objective_module_plan  # noqa: F401 - ensure objective module gate is registered
import app.tools.feedback_iteration_planner  # noqa: F401 - ensure feedback planner is registered
import app.tools.ligand_preprocess  # noqa: F401 - ensure ligand_preprocess is registered for submit tests
import app.tools.kcat_predict  # noqa: F401 - ensure kcat predictor is registered
import app.tools.mutation_epistasis_check  # noqa: F401 - ensure epistasis checker is registered
import app.tools.mutation_priority_score  # noqa: F401 - ensure mutation_priority_score is registered for direct execute tests
import app.tools.mutation_scan  # noqa: F401 - ensure mutation_scan is registered
import app.tools.predict_properties  # noqa: F401 - ensure physicochemical baseline tool is registered
import app.tools.protein_benchmark  # noqa: F401 - ensure protein_benchmark is registered
import app.tools.protssn_score  # noqa: F401 - ensure protssn proxy is registered
import app.tools.rosetta_ddg  # noqa: F401 - ensure rosetta_ddg is registered for direct execute tests
import app.tools.residue_numbering_gate  # noqa: F401 - ensure numbering gate is registered
import app.tools.scientific_claim_gate  # noqa: F401 - ensure claim gate is registered
import app.tools.wt_baseline_registry  # noqa: F401 - ensure WT baseline registry is registered
import app.tools.tool_capability_audit  # noqa: F401 - ensure capability audit is registered
import app.tools.bio_specialty_input_gate  # noqa: F401 - ensure specialty input gate is registered
import app.tools.alphafold2_folding  # noqa: F401 - ensure proxy capability output is registered
import app.tools.diffdock_docking  # noqa: F401 - ensure proxy capability output is registered
import app.tools.proteinmpnn_design  # noqa: F401 - ensure proxy capability output is registered
import app.tools.rfdiffusion_design  # noqa: F401 - ensure proxy capability output is registered
import app.tools.interproscan_sequence_submit  # noqa: F401 - ensure InterProScan sequence submit is registered
from app.api.files import _assert_file_download_access
from app.core.security import create_access_token
from app.models.user import User
from app.models.tool_call import ToolTaskAudit
from app.services.tool_task_store import (
    get_tool_artifact_owner,
    record_tool_artifact_owner,
    record_tool_task_cancel_requested,
    record_tool_task_owner,
    record_tool_task_runtime_policy,
)
from app.tools.registry import ToolRegistry

_CAPABILITY_CONTRACT_FIELDS = {
    "capability_status",
    "model",
    "version",
    "checkpoint_or_weight",
    "input_sha256",
    "runtime",
    "logs",
    "artifact_manifest",
    "scientific_boundary",
    "failure_reason",
}


async def test_tool_manifest_and_remediation_diagnostics_are_operator_actionable(client, session):
    user = User(
        email="tool-manifest@example.com",
        hashed_password=User.hash_password("password123"),
        name="Tool Manifest User",
    )
    session.add(user)
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    tools_response = await client.get("/api/tools")
    diagnostics_response = await client.get("/api/tools/diagnostics")

    assert tools_response.status_code == 200
    manifest = tools_response.json()["manifest"]
    assert manifest["tool_count"] == len(tools_response.json()["tools"])
    assert manifest["tool_names_sha256"]
    assert manifest["baseline"]["catalog_tool_count"] >= 55
    assert "pending_reconnect" in manifest["baseline"]["summary"]
    assert manifest["baseline"]["entries"]
    assert all(
        {"configured_fallback_tool", "fallback_tool", "fallback_level"} <= set(entry)
        for entry in manifest["baseline"]["entries"]
    )

    assert diagnostics_response.status_code == 200
    readiness = diagnostics_response.json()["remediation_readiness"]
    assert readiness["status"] == "ready_for_operator"
    assert "operator_approval_required" in readiness["blockers"]
    assert readiness["operator_actions"]


def _assert_capability_contract(result, expected_status):
    assert _CAPABILITY_CONTRACT_FIELDS <= set(result)
    assert result["capability_status"] == expected_status
    assert result["input_sha256"]
    assert isinstance(result["logs"], list)
    assert result["artifact_manifest"]["version"] == 1
    assert "total_count" in result["artifact_manifest"]
    assert result["scientific_boundary"]


_MUTANT_PREPARE_PDB = """ATOM      1  N   MET A 204      11.104  13.207   8.678  1.00 20.00           N
ATOM      2  CA  MET A 204      12.104  13.207   8.678  1.00 20.00           C
ATOM      3  C   MET A 204      12.504  14.607   8.678  1.00 20.00           C
ATOM      4  O   MET A 204      13.504  14.807   8.678  1.00 20.00           O
ATOM      5  CB  MET A 204      12.204  12.107   9.678  1.00 20.00           C
ATOM      6  CG  MET A 204      12.304  10.707   9.678  1.00 20.00           C
ATOM      7  SD  MET A 204      12.404   9.307   9.678  1.00 20.00           S
TER       8      MET A 204
END
"""


_ROSETTA_A10_PDB = """ATOM      1  N   ALA A  10      11.104  13.207   8.678  1.00 20.00           N
ATOM      2  CA  ALA A  10      12.104  13.207   8.678  1.00 20.00           C
ATOM      3  C   ALA A  10      12.504  14.607   8.678  1.00 20.00           C
ATOM      4  O   ALA A  10      13.504  14.807   8.678  1.00 20.00           O
TER       5      ALA A  10
END
"""


_LIGAND_2D_SDF = """5478883
  -OEChem-07082602182D

  2  1  0     0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
$$$$
"""

_LIGAND_3D_SDF = """5478883
  -OEChem-07082602183D

  2  1  0     0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.1000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.2000    0.0000   -0.1000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
$$$$
"""

_SD_388_SEQUENCE = (
    "APAQIVGRSTFQIDQVASGKVYKNGPMAMMQTYNKYAHVGAVAPAAVVAAAAAAQTGEVSANPEQYDESYLCPVTIGDQTLNLDFDTGSADLWVFSTLTPSSESTGHTLYNPADSGTEKQGYTWNITYGDGSGAAGVVYADKVVVGGVTATSQAVEAATSVSSEFTQDTKNDGLLGLAFSSINTVQPVQQTTFFDTVKDTLAKKLFTADLKKGAAGSYGFGYIDSSKYTGTITYVPVNNENGFWQFTAGGYSIGGGNGTSGSNATTGSIGTSIADTGTTLLLLPSNVVTAYYKQVSGASYNSAQGGYTYPCGATLPDFNVAIGGKTFVVPGTDLNYAPINSAGTTCFGGIQANTGIGFNIFGDIFLKSVYAVFDQTQSSPRLGFAEQS"
)


async def _create_user(session, email: str) -> User:
    user = User(
        email=email,
        hashed_password=User.hash_password("password123"),
        name="Tool User",
    )
    session.add(user)
    await session.flush()
    return user


async def test_tool_task_polling_rejects_unknown_task(client, session):
    user = await _create_user(session, "tool-task-owner@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/tools/tasks/missing-task-id")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tool task not found"


async def test_explicit_recompute_snapshots_owned_terminal_evidence_without_mutating_report(client, session, monkeypatch):
    user = await _create_user(session, "tool-recompute-owner@example.com")
    await session.commit()
    await record_tool_task_owner("recompute-ready-task", user.id, "blast_search")
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {"status": "completed", "result": {"status": "completed", "results_count": 1}},
    )

    response = await client.post(
        "/api/tools/analysis/recompute-decision",
        json={"analysis_fingerprint": "analysis-v1", "task_ids": ["recompute-ready-task"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recompute_ready"
    assert body["report_revision_created"] is False
    assert body["snapshot"]["snapshot_id"].startswith("ars_")
    assert body["snapshot"]["evidence_snapshot_fingerprint"] == body["evidence_snapshot_fingerprint"]
    assert body["task_snapshot"] == [{
        "task_id": "recompute-ready-task",
        "tool_name": "blast_search",
        "status": "completed",
        "result": {"status": "completed", "results_count": 1},
    }]


async def test_explicit_recompute_rejects_other_users_task(client, session):
    owner = await _create_user(session, "tool-recompute-owner2@example.com")
    intruder = await _create_user(session, "tool-recompute-intruder@example.com")
    await session.commit()
    await record_tool_task_owner("recompute-private-task", owner.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(intruder.id))

    response = await client.post(
        "/api/tools/analysis/recompute-decision",
        json={"task_ids": ["recompute-private-task"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Task does not belong to current user"


async def test_tool_task_polling_rejects_other_user_task(client, session):
    owner = await _create_user(session, "tool-task-owner@example.com")
    intruder = await _create_user(session, "tool-task-intruder@example.com")
    await session.commit()
    await record_tool_task_owner("owned-task-id", owner.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(intruder.id))

    response = await client.get("/api/tools/tasks/owned-task-id")

    assert response.status_code == 403
    assert response.json()["detail"] == "Task does not belong to current user"


async def test_tool_task_cancel_rejects_unknown_task(client, session):
    user = await _create_user(session, "tool-task-cancel-owner@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.post("/api/tools/tasks/missing-task-id/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tool task not found"


async def test_tool_task_cancel_rejects_other_user_task(client, session):
    owner = await _create_user(session, "tool-task-cancel-owner@example.com")
    intruder = await _create_user(session, "tool-task-cancel-intruder@example.com")
    await session.commit()
    await record_tool_task_owner("owned-cancel-task-id", owner.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(intruder.id))

    response = await client.post("/api/tools/tasks/owned-cancel-task-id/cancel")

    assert response.status_code == 403
    assert response.json()["detail"] == "Task does not belong to current user"


async def test_tool_task_cancel_revokes_owned_task(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-cancel-success@example.com")
    await session.commit()
    await record_tool_task_owner("owned-cancel-task-id", user.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(user.id))

    revoked = []
    monkeypatch.setattr("app.api.tools.cancel_task", lambda task_id: revoked.append(task_id) or True)

    response = await client.post("/api/tools/tasks/owned-cancel-task-id/cancel")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "owned-cancel-task-id"
    assert body["tool"] == "gromacs_md"
    assert body["status"] == "cancel_requested"
    assert body["cancel_requested_at"]
    assert revoked == ["owned-cancel-task-id"]


async def test_tool_task_submit_creates_persistent_audit(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-audit-submit@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr("app.api.tools.dispatch_tool", lambda tool_name, params: "audit-submit-task-id")

    response = await client.post(
        "/api/tools/gromacs_md/submit",
        json={
            "params": {
                "pdb_object_name": "uploads/user/input.pdb",
                "pdb_data": "ATOM large redacted payload",
                "simulation_time_ns": 0.1,
            }
        },
    )
    audit_response = await client.get("/api/tools/tasks/audit-submit-task-id/audit")
    list_response = await client.get("/api/tools/tasks/audits")

    assert response.status_code == 200
    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["task_id"] == "audit-submit-task-id"
    assert audit["tool"] == "gromacs_md"
    assert audit["status"] == "submitted"
    assert audit["queue"] == "md_cpu"
    assert audit["input_summary"]["values"]["pdb_object_name"] == "uploads/user/input.pdb"
    assert audit["input_summary"]["values"]["pdb_data"]["redacted"] is True
    assert list_response.status_code == 200


async def test_ligand_preprocess_preflight_blocks_missing_runtime_without_fake_3d(monkeypatch):
    monkeypatch.setattr("app.tools.ligand_preprocess.shutil.which", lambda name: None)

    result = await ToolRegistry.execute(
        "ligand_preprocess",
        {"sdf_data": _LIGAND_2D_SDF, "stages": ["preflight", "generate_3d"], "store_outputs": False},
    )

    assert result["status"] == "blocked"
    assert result["sdf"]["is_2d_sdf"] is True
    assert result["sdf"]["atom_count"] == 2
    assert result["sdf"]["bond_count"] == 1
    assert result["stage_results"][0]["stage"] == "preflight"
    assert "conformer_generation" in result["stage_results"][0]["missing_requirements"]
    generate = result["stage_results"][1]
    assert generate["stage"] == "generate_3d"
    assert generate["status"] == "blocked"
    assert generate["blocked_reason"] == "openbabel_not_installed"
    assert result["stage_readiness"]["blocked"] == ["preflight", "generate_3d"]
    assert result["stage_readiness"]["by_stage"]["generate_3d"]["blocked_reason"] == "openbabel_not_installed"
    assert result["stage_readiness"]["can_enter_docking"] is False
    assert result["stage_readiness"]["can_enter_gromacs_complex_md"] is False
    assert result["scientific_boundary"]["input_2d_sdf_can_enter_md_directly"] is False


async def test_mutation_priority_score_attaches_lipase_evidence(monkeypatch):
    def fake_lipase_context(**kwargs):
        return {
            "status": "ready",
            "requested_mutations": kwargs.get("mutations") or [],
            "requested_positions": kwargs.get("positions") or [],
            "exact_mutation_matches": [
                {
                    "mutation_code": "D223K",
                    "position": 223,
                    "paper_key": "Xie_2014",
                    "claim_group": "kinetic_stability",
                    "evidence_level": "article_level",
                    "claim_summary": "test evidence",
                }
            ],
            "position_matches": [{"mutation_code": "D223G", "position": 223, "paper_key": "Xie_2014"}],
            "counts": {"exact_mutation_matches": 1, "position_matches": 1, "search_matches": 0},
        }

    monkeypatch.setattr("app.tools.mutation_priority_score.build_lipase_evidence_context", fake_lipase_context)
    sequence = "A" * 222 + "D" + "A" * 20

    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": sequence,
            "engineering_goal": "ph_raising",
            "include_lipase_evidence": True,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [],
            },
            "objective_module_plan": {"status": "ready", "candidate_output_allowed": True},
        },
    )

    assert result["strategy"]["goal"] == "ph_raising"
    assert result["strategy"]["objective"]
    assert result["strategy"]["experiment_plan"][0]["priority"] == "P1"
    assert result["lipase_evidence_context"]["status"] == "ready"
    candidate = next(item for item in result["tier_1_candidates"] if item["position"] == 223)
    assert candidate["lipase_position_evidence_count"] == 1
    assert candidate["experiment_priority"] in {"P1", "P2", "P3", "No-Go"}
    assert "risk_flags" in candidate
    evidence = next(item for item in candidate["recommended_mutations"] if item["mutation"] == "D223K")["lipase_evidence"]
    assert evidence["exact_match_count"] == 1
    assert evidence["matches"][0]["paper_key"] == "Xie_2014"


async def test_mutation_priority_score_attaches_wet_lab_calibration_context_without_direct_validation():
    sequence = "A" * 222 + "D" + "A" * 20

    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": sequence,
            "engineering_goal": "ph_raising",
            "include_lipase_evidence": False,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [],
            },
            "objective_module_plan": {"status": "ready", "candidate_output_allowed": True},
            "wet_lab_calibration_summary": {
                "objective": "ph_raising",
                "assay_key": "specific_activity|pNP-C8|7.0|37",
                "dataset_fingerprint": "calib123",
                "measured_variant_count": 3,
                "go_count": 2,
                "watch_count": 1,
                "no_go_count": 0,
                "hit_rate": 0.6667,
                "data_quality_grade": "feedback_supported",
                "evidence_level": "wet_lab_feedback",
            },
        },
    )

    context = result["wet_lab_calibration_context"]
    assert context["evidence_level"] == "wet_lab_feedback"
    assert context["candidate_scope"] == "project_level_calibration_not_direct_variant_validation"

    candidate = next(item for item in result["tier_1_candidates"] if item["position"] == 223)
    assert candidate["calibration_evidence_status"] == "wet_lab_feedback"
    assert candidate["candidate_evidence_status"] != "experimental_supported"
    assert any("不能升级为湿实验级候选" in flag for flag in candidate["risk_flags"])
    assert result["experiment_design_table"][0]["calibration_evidence_status"] == "wet_lab_feedback"
    assert all(row.get("candidate_evidence_status") != "experimental_supported" for row in result["experiment_design_table"])


async def test_identity_profile_records_peptidase_a1_as_motif_candidate_only():
    identity = await ToolRegistry.execute(
        "enzyme_identity_profile",
        {"sequence": _SD_388_SEQUENCE},
    )

    # Two D(T/S)G(T/S) hits are a family clue, not curated evidence: the profile
    # must not promote them to an identified family or to catalytic residue numbers.
    assert identity["identity_status"] == "candidate"
    assert identity["identity_basis"] == "motif_heuristic"
    assert identity["guardrail"]["status"] == "blocked"
    top = identity["family_candidates"][0]
    assert top["name"] == "Peptidase A1 / aspartic peptidase family"
    assert top["evidence_tier"] == "motif"
    assert top["confidence"] <= 0.6
    assert identity["ec_candidates"][0]["ec"] == "3.4.23.-"
    # Only the lobe-separated pair is protected; 114 sits 28 residues from 86
    # and cannot be the second catalytic Asp.
    protected = identity["protected_positions"]
    assert 86 in protected and 275 in protected
    assert 114 not in protected
    dyad = {
        item["position"]
        for item in identity["key_residues"]
        if item.get("role", "").startswith("candidate catalytic acid")
    }
    assert dyad == {86, 275}
    assert any("No direct InterProScan" in item for item in identity["missing_evidence"])
    assert any(item["type"] == "family_evidence_conflict" for item in identity["conflicts"])

    benchmark = await ToolRegistry.execute(
        "protein_benchmark",
        {"query_sequence": _SD_388_SEQUENCE, "identity_profile": identity},
    )

    assert benchmark["foundation_gate"]["status"] == "blocked"
    assert benchmark["catalytic_residues"]["known"] is False
    assert benchmark["family_motifs"] == []


async def test_identity_profile_identified_requires_non_heuristic_family_evidence():
    # Contract invariant: whatever a producer declares, "identified" needs a
    # family candidate from a qualifying tier at or above the threshold.
    heuristic_bundle = {
        "record_provenance": {"is_reviewed": True, "source_db": "UniProtKB/Swiss-Prot"},
        "interpro": {
            "annotations": [
                {
                    "source": "heuristic",
                    "entry_type": "family",
                    "name": "Peptidase A1 / aspartic peptidase family",
                    "start_pos": 1,
                    "end_pos": len(_SD_388_SEQUENCE),
                }
            ]
        },
    }
    heuristic = await ToolRegistry.execute(
        "enzyme_identity_profile",
        {"sequence": _SD_388_SEQUENCE, "evidence_bundle": heuristic_bundle},
    )
    assert heuristic["identity_status"] != "identified"
    assert heuristic["guardrail"]["status"] == "blocked"

    bare = await ToolRegistry.execute("enzyme_identity_profile", {"sequence": _SD_388_SEQUENCE})
    for profile in (heuristic, bare):
        if profile["identity_status"] == "identified":
            qualifying = [
                item for item in profile["family_candidates"]
                if item.get("entry_type") == "family"
                and item.get("evidence_tier") in {"curated", "template"}
                and float(item.get("confidence", 0.0)) >= 0.7
            ]
            assert qualifying, "identified status must rest on qualifying-tier family evidence"


async def test_sd_388_outputs_ready_mutation_experiment_table_when_foundation_and_objective_are_ready():
    # The ready path requires curated evidence: a motif hit alone stays a
    # candidate, so this fixture supplies a reviewed InterPro family call and a
    # verified numbering mapping.
    identity = await ToolRegistry.execute(
        "enzyme_identity_profile",
        {
            "sequence": _SD_388_SEQUENCE,
            "evidence_bundle": {
                "interpro": {
                    "annotations": [
                        {
                            "source": "InterProScan",
                            "entry_type": "family",
                            "name": "Peptidase A1 / aspartic peptidase family",
                            "interpro_id": "IPR001461",
                            "start_pos": 1,
                            "end_pos": len(_SD_388_SEQUENCE),
                        }
                    ]
                },
                "record_provenance": {"is_reviewed": True, "source_db": "UniProtKB/Swiss-Prot"},
            },
            "residue_mapping": {"numbering_registry_status": "ready", "numbering_registry_rows": []},
        },
    )
    assert identity["identity_status"] == "identified"
    assert identity["identity_basis"] == "curated_family"
    assert identity["guardrail"]["status"] == "ready"
    objective = await ToolRegistry.execute(
        "enzyme_objective_module_plan",
        {
            "objective": "thermostability",
            "identity_profile": identity,
            "assay_context": {"tm": True},
        },
    )
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "thermostability",
            "identity_profile": identity,
            "objective_module_plan": objective,
            "include_lipase_evidence": False,
        },
    )

    assert objective["status"] == "ready"
    assert result["identity_gate"]["status"] == "passed"
    assert result["candidate_table_status"] == "ready"
    assert result["experiment_design_table"], "bench-facing mutation site table is required"
    first = result["experiment_design_table"][0]
    assert first["experiment_priority"] in {"P1", "P2", "P3"}
    assert first["recommended_mutations"]
    assert first["mutation_logic"]
    assert first["expected_effect"]
    assert first["position"] not in {86, 275}
    assert all(row["position"] not in {86, 275} for row in result["experiment_design_table"])


async def test_unknown_family_with_clear_goal_blocks_candidate_table_until_identity_is_confirmed():
    identity = await ToolRegistry.execute(
        "enzyme_identity_profile",
        {"sequence": "M" * 120},
    )
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": "M" * 120,
            "engineering_goal": "activity",
            "identity_profile": identity,
            "include_lipase_evidence": False,
        },
    )

    assert identity["identity_status"] == "unresolved"
    assert identity["guardrail"]["status"] == "blocked"
    assert result["identity_gate"]["status"] == "blocked"
    assert result["candidate_table_status"] == "blocked_by_identity_gate"
    assert result["candidate_table_boundary"]["mode"] == "blocked"
    assert result["experiment_design_table"] == []
    assert result["tier_2_candidates"] == []


async def test_protein_benchmark_blocks_family_hints_without_identity_profile():
    result = await ToolRegistry.execute(
        "protein_benchmark",
        {
            "query_sequence": "M" * 300,
            "known_family": "GH13",
            "enzyme_type": "amylase",
        },
    )

    assert result["status"] == "blocked"
    assert result["capability_status"] == "foundation_dependent_explainer"
    assert result["evidence_level"] == "BLOCKED"
    assert "不得输出家族特异工程建议" in result["report_boundary"]
    assert result["foundation_gate"]["status"] == "blocked"
    assert result["foundation_gate"]["user_supplied_context"]["known_family"] == "GH13"
    assert result["family"]["identified"] is None
    assert result["known_engineering_successes"] == []
    assert result["family_motifs"] == []
    assert result["catalytic_residues"]["known"] is False
    assert result["engineering_targets"]["thermostability"] == []
    assert any("enzyme_identity_profile" in item for item in result["recommendations"][0]["plan"])


async def test_protein_benchmark_blocks_identity_profile_with_failed_guardrail():
    result = await ToolRegistry.execute(
        "protein_benchmark",
        {
            "query_sequence": "M" * 120,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "blocked"},
                "family_candidates": [
                    {
                        "name": "Alpha amylase",
                        "accession": "IPR006046",
                        "entry_type": "family",
                        "confidence": 0.95,
                    }
                ],
                "protected_positions": [],
            },
        },
    )

    assert result["status"] == "blocked"
    assert result["capability_status"] == "foundation_dependent_explainer"
    assert result["evidence_level"] == "BLOCKED"
    assert result["family"]["name"] == "Unknown enzyme family"
    assert result["benchmark_metrics"]["reason"] == "family_not_confirmed"


async def test_scientific_claim_gate_blocks_unsupported_summary_claims():
    result = await ToolRegistry.execute(
        "scientific_claim_gate",
        {
            "report_section": "summary",
            "claims": [
                {"claim_id": "C001", "claim": "PDB residue mapping is verified.", "status": "SUPPORTED"},
                {"claim_id": "C002", "claim": "Risk threshold 0.60 is validated.", "status": "MISSING"},
                {"claim_id": "C003", "claim": "The formula is calibrated.", "status": "CONFLICTING"},
                {"claim_id": "C004", "claim": "This is a useful design rule.", "status": "DESIGN_HYPOTHESIS"},
            ],
        },
    )

    assert result["status"] == "blocked"
    assert [item["claim_id"] for item in result["allowed_claims"]] == ["C001"]
    assert {item["claim_id"] for item in result["blocked_claims"]} == {"C002", "C003"}
    assert [item["claim_id"] for item in result["downgraded_claims"]] == ["C004"]
    actions = {item["claim_id"]: item["report_action"] for item in result["audit_table"]}
    assert actions["C002"] == "block"
    assert actions["C004"] == "downgrade_to_methods_as_uncalibrated_hypothesis"


async def test_scientific_claim_gate_requires_ready_wt_baseline_registry():
    result = await ToolRegistry.execute(
        "scientific_claim_gate",
        {
            "report_section": "summary",
            "claims": [
                {
                    "claim_id": "WT_MISSING",
                    "claim": "Specific activity improved.",
                    "status": "SUPPORTED",
                    "requires_wt_baseline": True,
                    "wt_baseline_registry": {"status": "missing"},
                },
                {
                    "claim_id": "WT_READY",
                    "claim": "Specific activity improved under the matched assay.",
                    "status": "SUPPORTED",
                    "requires_wt_baseline": True,
                    "wt_baseline_registry": {"status": "ready"},
                },
            ],
        },
    )

    assert result["status"] == "blocked"
    assert [item["claim_id"] for item in result["allowed_claims"]] == ["WT_READY"]
    blocked = result["blocked_claims"][0]
    assert blocked["claim_id"] == "WT_MISSING"
    assert blocked["reason"] == "claim requires an exact-condition WT baseline registry with status=ready"


async def test_wt_baseline_registry_tool_exposes_report_contract_and_blocks_approximate_substitution(session):
    from app.models.domain import EnzymeRecord, KineticParameter

    enzyme = EnzymeRecord(
        uniprot_id="WTTOOL1",
        entry_name="WTTOOL1_TEST",
        sequence="MSTNPKPQRKTK",
        seq_length=12,
        protein_name="WT tool test enzyme",
    )
    session.add(enzyme)
    await session.flush()
    session.add(
        KineticParameter(
            enzyme_id=enzyme.id,
            source_db="brenda",
            param_type="specific_activity",
            substrate_name="starch",
            value=12.0,
            unit="U/mg",
            ph=5.0,
            temperature_c=50.0,
            mutant="wild-type",
            literature_ref="PMID:1",
        )
    )
    await session.commit()

    result = await ToolRegistry.execute(
        "wt_baseline_registry",
        {
            "uniprot_id": "WTTOOL1",
            "metric": "specific_activity",
            "substrate_name": "starch",
            "ph": 5.0,
            "temperature_c": 50.0,
            "buffer": "sodium acetate",
            "protein_preparation": "purified_enzyme",
            "batch_id": "B-01",
        },
        internal_params={"_session": session},
    )

    assert result["status"] == "missing"
    assert result["report_contract"]["schema_version"] == "wt_baseline_report_contract_v1"
    assert result["report_contract"]["ready_for_comparison"] is False
    assert result["report_contract"]["approximate_condition_substitution_allowed"] is False
    assert result["report_contract"]["nearest_condition_fallback_allowed"] is False
    assert result["claim_context"]["claim_status"] == "MISSING"
    assert result["claim_context"]["baseline_status"] == "missing"


async def test_scientific_claim_gate_allows_weak_body_claims_but_blocks_runtime_unverified():
    result = await ToolRegistry.execute(
        "scientific_claim_gate",
        {
            "report_section": "body",
            "claims": [
                {"claim_id": "C001", "claim": "Expression evidence is weak.", "status": "WEAK"},
                {"claim_id": "C002", "claim": "AF3 really ran.", "status": "RUNTIME_UNVERIFIED"},
            ],
        },
    )

    assert result["status"] == "blocked"
    assert [item["claim_id"] for item in result["allowed_claims"]] == ["C001"]
    assert [item["claim_id"] for item in result["blocked_claims"]] == ["C002"]


async def test_enzyme_objective_module_plan_blocks_without_objective_evidence():
    identity = {
        "identity_status": "identified",
        "guardrail": {"status": "ready"},
        "protected_positions": [86, 275],
    }
    result = await ToolRegistry.execute(
        "enzyme_objective_module_plan",
        {
            "objective": "ph_lowering",
            "identity_profile": identity,
            "assay_context": {},
        },
    )

    assert result["status"] == "blocked"
    assert result["objective"] == "ph_profile"
    assert result["foundation_gate"]["status"] == "ready"
    assert result["candidate_output_allowed"] is False
    assert any("pH curve" in item for item in result["missing_evidence"])
    assert any("pH4.5/pH6.0 ratio" in item for item in result["forbidden_shortcuts"])


async def test_enzyme_objective_module_plan_allows_specificity_with_comparator_substrate():
    result = await ToolRegistry.execute(
        "enzyme_objective_module_plan",
        {
            "objective": "substrate_specificity",
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [100, 150],
            },
            "assay_context": {
                "target_substrate": "starch",
                "off_target_substrate": "pullulan",
            },
        },
    )

    assert result["status"] == "ready"
    assert "selectivity ratio" in result["validation_metrics"]


async def test_enzyme_objective_module_plan_keeps_multi_objective_modules():
    identity = {
        "identity_status": "identified",
        "guardrail": {"status": "ready"},
        "protected_positions": [86, 275],
    }
    result = await ToolRegistry.execute(
        "enzyme_objective_module_plan",
        {
            "objective": "activity",
            "objective_signals": ["activity", "thermostability"],
            "identity_profile": identity,
            "assay_context": {
                "specific_activity": True,
                "protein_normalized": True,
                "tm": True,
            },
        },
    )

    assert result["status"] == "ready"
    assert result["multi_objective"] is True
    assert result["objective_signals"] == ["specific_activity", "thermostability"]
    modules = {item["objective"]: item for item in result["objective_modules"]}
    assert {"specific_activity", "thermostability"} <= set(modules)
    assert any("specific activity" in item for item in result["combined_validation_metrics"])
    assert any("Tm" in item for item in result["combined_validation_metrics"])
    assert any("total broth" in item for item in result["forbidden_shortcuts"])
    assert any("heat challenge" in item for item in result["forbidden_shortcuts"])
    assert result["candidate_output_allowed"] is True


async def test_mutation_priority_keeps_experimental_table_when_objective_context_is_incomplete():
    sequence = "M" + ("A" * 90) + "D" + ("S" * 90) + "E" + ("T" * 90)
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": sequence,
            "engineering_goal": "thermostability",
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [92, 183],
            },
            "objective_module_plan": {
                "status": "blocked",
                "objective": "thermostability",
                "module": "thermostability",
                "candidate_output_allowed": False,
                "missing_evidence": ["Provide baseline Tm, half-life, or thermal residual activity context."],
            },
            "include_lipase_evidence": False,
        },
    )

    assert result["identity_gate"]["status"] == "passed"
    assert result["candidate_table_status"] == "blocked_by_objective_gate"
    assert result["experiment_design_table"] == []
    assert result["tier_2_candidates"] == []


async def test_proxy_predictors_do_not_claim_real_inference():
    kcat = await ToolRegistry.execute(
        "kcat_predict",
        {"protein_sequence": "M" + ("A" * 80), "substrate_smiles": "CCO"},
    )
    assert kcat["is_real_inference"] is False
    assert kcat["capability_status"] == "proxy"
    assert kcat["evidence_level"] == "DESIGN_HYPOTHESIS"
    assert "中高催化效率" not in kcat["efficiency_assessment"]
    assert "典型工业酶" not in kcat["efficiency_assessment"]
    assert "不能代表真实比活力" in kcat["efficiency_assessment"]
    assert "不得写成校准 kcat" in kcat["report_boundary"]

    protssn = await ToolRegistry.execute(
        "protssn_score",
        {"sequence": "M" + ("A" * 20), "mutations": ["A10G"]},
    )
    assert protssn["is_real_inference"] is False
    assert protssn["capability_status"] == "proxy"
    assert protssn["evidence_level"] == "DESIGN_HYPOTHESIS"
    assert protssn["candidate_table_status"] == "requires_identity_numbering_objective_gate"
    assert "不得单独决定突变优先级" in protssn["report_boundary"]
    assert "优先改造候选" not in str(protssn["mutations"])

    scan = await ToolRegistry.execute(
        "mutation_scan",
        {"sequence": "M" + ("A" * 20), "positions": [10], "scan_type": "saturation"},
    )
    assert scan["capability_status"] == "proxy"
    assert scan["evidence_level"] == "DESIGN_HYPOTHESIS"
    assert scan["candidate_table_status"] == "requires_identity_numbering_objective_gate"
    assert "不得把扫描结果写成可排单突变候选表" in scan["report_boundary"]


async def test_predict_properties_labels_background_baseline_boundary():
    result = await ToolRegistry.execute(
        "predict_properties",
        {"sequence": "M" + ("A" * 80)},
    )

    assert result["capability_status"] == "physicochemical_baseline"
    assert result["evidence_level"] == "BACKGROUND_BASELINE"
    assert "不能单独证明热稳定性、比活力、酶身份或突变增益" in result["report_boundary"]


async def test_named_model_mvp_tools_emit_proxy_capability_status():
    af2 = await ToolRegistry.execute(
        "alphafold2_folding",
        {"sequence": "M" + ("A" * 30)},
    )
    _assert_capability_contract(af2, "proxy")
    assert af2["capability_status"] == "proxy"
    assert af2["is_real_inference"] is False
    assert "official AlphaFold2" in af2["report_boundary"]

    rf = await ToolRegistry.execute(
        "rfdiffusion_design",
        {"length": 30, "num_designs": 1},
    )
    _assert_capability_contract(rf, "proxy")
    assert rf["capability_status"] == "proxy"
    assert rf["is_real_inference"] is False
    assert "RFdiffusion" in rf["report_boundary"]

    pdb = "\n".join([
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C",
        "ATOM      2  CA  GLY A   2       1.000   0.000   0.000  1.00 20.00           C",
        "ATOM      3  CA  SER A   3       2.000   0.000   0.000  1.00 20.00           C",
    ])
    diffdock = await ToolRegistry.execute(
        "diffdock_docking",
        {"ligand_smiles": "CCO", "protein_pdb": pdb},
    )
    _assert_capability_contract(diffdock, "proxy")
    assert diffdock["capability_status"] == "proxy"
    assert diffdock["is_real_inference"] is False
    assert "Do not interpret proxy score as Kd" in diffdock["report_boundary"]

    mpnn = await ToolRegistry.execute(
        "proteinmpnn_design",
        {"pdb_structure": pdb, "num_sequences": 1},
    )
    _assert_capability_contract(mpnn, "proxy")
    assert mpnn["is_real_inference"] is False
    assert "ProteinMPNN" in mpnn["scientific_boundary"]


async def test_gromacs_blocked_result_emits_capability_contract(monkeypatch):
    monkeypatch.setattr("app.tools.gromacs_md._find_gmx", lambda: None)

    result = await ToolRegistry.execute(
        "gromacs_md",
        {"pdb_data": _ROSETTA_A10_PDB, "simulation_time_ns": 0.1},
    )

    _assert_capability_contract(result, "blocked")
    assert result["status"] == "failed"
    assert result["error_code"] == "GROMACS_NOT_INSTALLED"
    assert result["failure_reason"] == "GROMACS_NOT_INSTALLED"
    assert result["is_real_md"] is False


async def test_tool_capability_audit_labels_proxy_and_runtime_gated_tools():
    result = await ToolRegistry.execute(
        "tool_capability_audit",
        {"tool_names": ["rfdiffusion_design", "rosetta_ddg", "mutation_scan", "unknown_tool"]},
    )

    assert result["status"] == "partial"
    by_tool = {item["tool"]: item for item in result["capabilities"]}
    assert by_tool["rfdiffusion_design"]["capability_status"] == "proxy"
    assert by_tool["rfdiffusion_design"]["report_action"] == "label_as_proxy_or_block_until_artifacts_exist"
    assert by_tool["rosetta_ddg"]["capability_status"] == "real_runtime_gated"
    assert by_tool["mutation_scan"]["capability_status"] == "proxy"
    assert "not a candidate table" in by_tool["mutation_scan"]["boundary"]
    assert by_tool["unknown_tool"]["report_action"] == "block_report_grade_claims"


async def test_tool_capability_audit_registers_residue_site_tools():
    result = await ToolRegistry.execute(
        "tool_capability_audit",
        {"tool_names": ["catalytic_site_lookup", "build_site_structure_function_features"]},
    )
    assert result["status"] == "ready"
    by_tool = {item["tool"]: item for item in result["capabilities"]}
    assert by_tool["catalytic_site_lookup"]["capability_status"] == "curated_or_motif_guardrail"
    assert by_tool["build_site_structure_function_features"]["capability_status"] == "residue_geometry_feature_table"
    assert result["unknown_tools"] == []


async def test_bio_specialty_input_gate_blocks_incomplete_muc16_offtarget():
    result = await ToolRegistry.execute(
        "bio_specialty_input_gate",
        {
            "workflow": "MUC16 纳米抗体脱靶",
            "inputs": {"target_antigen": "MUC16"},
        },
    )

    assert result["status"] == "blocked"
    assert result["workflow"] == "human_membrane_offtarget"
    assert result["missing_required"] == ["binder_type"]
    assert any("HumanProteinProfile" in item for item in result["data_contracts"])
    assert any("full-length similarity alone" in item for item in result["blocked_claims"])


async def test_bio_specialty_input_gate_allows_antibody_humanization_inputs_without_affinity_claims():
    result = await ToolRegistry.execute(
        "bio_specialty_input_gate",
        {
            "workflow": "antibody_humanization",
            "inputs": {
                "vh_sequence": "QVQLQQSGAE",
                "vl_sequence": "QIVLTQSPAI",
                "light_chain_type": "kappa",
            },
        },
    )

    assert result["status"] == "ready"
    assert result["workflow"] == "antibody_humanization"
    assert any("AntibodyChainProfile" in item for item in result["data_contracts"])
    assert any("affinity retention" in item for item in result["blocked_claims"])


async def test_bio_specialty_input_gate_returns_schema_only_contracts_not_claim_evidence():
    result = await ToolRegistry.execute(
        "bio_specialty_input_gate",
        {
            "workflow": "human_membrane_offtarget",
            "inputs": {"target_antigen": "MUC16", "binder_type": "nanobody"},
        },
    )

    assert result["status"] == "ready"
    assert result["evidence_status"] == "schema_only_no_retrieval"
    assert result["claim_eligible"] is False
    assert result["model_claim_ready"] is False
    assert result["release_ready"] is False
    by_name = {item["name"]: item for item in result["data_contract_schemas"]}
    assert by_name["HumanProteinProfile"]["schema_only"] is True
    assert "uniprot_accession" in by_name["HumanProteinProfile"]["required_fields"]


async def test_scientific_claim_gate_blocks_supported_claim_when_required_schema_missing():
    result = await ToolRegistry.execute(
        "scientific_claim_gate",
        {
            "report_section": "summary",
            "required_schema_contracts": ["HumanProteinProfile"],
            "claims": [
                {
                    "claim_id": "C_SCHEMA",
                    "claim": "MUC16 extracellular target profile is supported.",
                    "status": "SUPPORTED",
                }
            ],
        },
    )

    assert result["status"] == "blocked"
    assert result["allowed_claims"] == []
    assert result["model_claim_ready"] is False
    assert result["release_ready"] is False
    blocked = result["blocked_claims"][0]
    assert blocked["claim_id"] == "C_SCHEMA"
    assert blocked["reason"] == "required schema contract is missing or incomplete"
    assert blocked["schema_audits"][0]["status"] == "blocked"
    assert blocked["schema_audits"][0]["claim_eligible"] is False


async def test_identity_profile_consumes_curated_annotation_bundle_with_verified_coordinates():
    identity = await ToolRegistry.execute(
        "enzyme_identity_profile",
        {
            "sequence": "M" * 300,
            "evidence_bundle": {
                "coordinate_system": {"status": "verified"},
                "protein": {
                    "uniprot_id": "CURATED_GH13",
                    "ec_numbers": [
                        {"ec": "3.2.1.1", "name": "Alpha-amylase", "primary": True},
                    ],
                    "cofactors": ["Calcium ion"],
                },
                "interpro": {
                    "annotations": [
                        {
                            "interpro_id": "IPR006046",
                            "name": "Alpha amylase",
                            "entry_type": "family",
                            "source": "interpro",
                            "start_pos": 1,
                            "end_pos": 300,
                            "evidence": "interpro_api",
                        },
                        {
                            "interpro_id": "IPR006047",
                            "name": "Glycosyl hydrolase family 13, catalytic domain",
                            "entry_type": "domain",
                            "source": "interpro",
                            "start_pos": 20,
                            "end_pos": 270,
                            "evidence": "interpro_api",
                        },
                    ],
                },
                "catalytic_sites": {
                    "curated_sites": [
                        {
                            "source": "UniProtKB",
                            "mechanism_name": "Curated catalytic center",
                            "reaction_text": "Starch hydrolysis",
                            "residues": [
                                {"position": 100, "residue": None, "role": "Nucleophile", "confidence": 0.9},
                            ],
                        },
                    ],
                },
                "signal_peptide": {
                    "has_signal_peptide": False,
                    "confidence": 0.92,
                    "model": "curated_test",
                    "cache": {"source": "database"},
                },
            },
        },
    )

    assert identity["identity_status"] == "identified"
    assert identity["family_candidates"][0]["accession"] == "IPR006046"
    assert identity["ec_candidates"][0]["ec"] == "3.2.1.1"
    assert identity["functional_domains"][0]["accession"] == "IPR006047"
    assert identity["protected_positions"] == [100]
    assert identity["cofactors"] == ["Calcium ion"]
    assert identity["numbering"]["status"] == "verified_for_input_sequence"
    assert identity["guardrail"]["status"] == "ready"


async def test_identity_profile_blocks_unmapped_curated_residue_coordinates():
    identity = await ToolRegistry.execute(
        "enzyme_identity_profile",
        {
            "sequence": "M" * 120,
            "evidence_bundle": {
                "coordinate_system": {"status": "mapping_required"},
                "interpro": {
                    "annotations": [
                        {
                            "interpro_id": "IPR006046",
                            "name": "Alpha amylase",
                            "entry_type": "family",
                            "source": "interpro",
                            "start_pos": 1,
                            "end_pos": 120,
                        },
                    ],
                },
                "catalytic_sites": {
                    "curated_sites": [
                        {
                            "source": "UniProtKB",
                            "residues": [
                                {"position": 100, "residue": None, "role": "Nucleophile", "confidence": 0.9},
                            ],
                        },
                    ],
                },
            },
        },
    )

    assert identity["identity_status"] == "identified"
    assert identity["protected_positions"] == []
    assert identity["key_residues"][0]["status"] == "protected_pending_numbering_confirmation"
    assert identity["numbering"]["status"] == "external_annotation_mapping_required"
    assert identity["guardrail"]["status"] == "blocked"


async def test_identity_profile_does_not_identify_from_superfamily_only():
    identity = await ToolRegistry.execute(
        "enzyme_identity_profile",
        {
            "sequence": "M" * 120,
            "evidence_bundle": {
                "coordinate_system": {"status": "verified"},
                "interpro": {
                    "annotations": [
                        {
                            "interpro_id": "IPR017853",
                            "name": "Glycoside hydrolase superfamily",
                            "entry_type": "homologous_superfamily",
                            "source": "interpro",
                            "start_pos": 1,
                            "end_pos": 120,
                        },
                    ],
                },
            },
        },
    )

    assert identity["identity_status"] == "unresolved"
    assert identity["guardrail"]["status"] == "blocked"
    assert identity["family_candidates"][0]["entry_type"] == "homologous_superfamily"


async def test_enzyme_function_suppresses_single_lipase_motif_call():
    result = await ToolRegistry.execute(
        "enzyme_function",
        {"sequence": "GYSIG"},
    )

    assert result["capability_status"] == "proxy"
    assert result["evidence_level"] == "DESIGN_HYPOTHESIS"
    assert "不得写成已确认 EC" in result["report_boundary"]
    predictions = result["predictions"]
    assert not any(pred.get("ec_number") == "3.1.1.3" for pred in predictions)
    if predictions:
        assert predictions[0]["ec_number"] != "3.1.1.3"


async def test_mutation_priority_score_exploratory_without_confirmed_identity_when_goal_is_clear():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "activity",
            "identity_profile": {
                "identity_status": "candidate",
                "guardrail": {"status": "blocked"},
                "protected_positions": [86, 275],
            },
        },
    )

    assert result["identity_gate"]["status"] == "blocked"
    assert result["summary"]["identity_gate_status"] == "blocked"
    assert result["summary"]["tier_1_count"] == 0
    assert result["summary"]["tier_2_count"] == 0
    assert result["candidate_table_status"] == "blocked_by_identity_gate"
    assert result["tier_1_candidates"] == []
    assert result["tier_2_candidates"] == []
    assert result["experiment_design_table"] == []
    assert result["all_positions"] == []


async def test_mutation_priority_score_exploratory_without_identity_profile_when_goal_is_clear():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "activity",
            "include_lipase_evidence": False,
        },
    )

    assert result["identity_gate"]["status"] == "blocked"
    assert result["summary"]["tier_1_count"] == 0
    assert result["candidate_table_status"] == "blocked_by_identity_gate"
    assert result["tier_1_candidates"] == []
    assert result["tier_2_candidates"] == []
    assert result["experiment_design_table"] == []


async def test_mutation_priority_score_emits_coordinate_bound_hypotheses_without_identity():
    sequence = _SD_388_SEQUENCE
    mapping = [
        {
            "user_sequence_position": position,
            "target_position": position + 1,
            "target_chain_id": "A",
            "target_residue_aa": aa,
            "confidence": "exact",
            "source_scheme": "coordinate_sequence",
            "target_scheme": "pdb_author",
        }
        for position, aa in enumerate(sequence, start=1)
    ]
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": sequence,
            "engineering_goal": "activity",
            "sequence_provenance": "pdb_coordinate_derived",
            "pdb_coordinate_mapping": mapping,
            "chain_id": "A",
            "include_lipase_evidence": False,
        },
    )

    assert result["candidate_table_status"] == "blocked_by_identity_gate"
    assert result["candidate_table_boundary"]["mode"] == "exploratory"
    assert result["candidate_table_boundary"]["evidence_level"] == "computational_hypothesis"
    assert result["tier_2_candidates"]
    candidate = result["tier_2_candidates"][0]
    assert candidate["candidate_status"] == "exploratory"
    assert candidate["experiment_priority"] == "P2-探索"
    assert candidate["pdb_position"].startswith("A:")
    assert candidate["candidate_evidence_status"] == "computational_hypothesis"
    assert result["candidate_decision"]["candidate_output_allowed"] is False
    assert result["experiment_design_table"] == []
    assert result["all_positions"] == []


async def test_mutation_priority_score_thermostability_penalizes_terminal_construct_noise():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "thermostability",
            "include_lipase_evidence": False,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [86, 114, 275],
            },
            "objective_module_plan": {
                "status": "blocked",
                "candidate_output_allowed": False,
                "missing_evidence": ["baseline Tm"],
            },
        },
    )

    positions = [row["position"] for row in result["experiment_design_table"][:12]]
    assert positions == []


async def test_mutation_priority_score_keeps_activity_stability_ranking_mode():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "activity",
            "objective_signals": ["activity", "thermostability"],
            "include_lipase_evidence": False,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [86, 114, 275],
            },
            "objective_module_plan": {
                "status": "ready",
                "objective": "specific_activity",
                "objective_signals": ["specific_activity", "thermostability"],
                "multi_objective": True,
                "objective_modules": [
                    {"objective": "specific_activity", "module": "specific_activity"},
                    {"objective": "thermostability", "module": "thermostability"},
                ],
                "candidate_output_allowed": True,
                "missing_evidence": [],
            },
        },
    )

    assert result["multi_objective"] is True
    assert result["ranking_mode"] == "activity_stability"
    assert result["strategy"]["goal"] == "activity_stability"
    assert "双指标共同验证" in result["strategy"]["objective"]
    assert result["objective_gate"]["multi_objective"] is True
    assert len(result["objective_gate"]["objective_modules"]) == 2
    assert result["experiment_design_table"]
    first_action = result["experiment_design_table"][0]["experiment_action"]
    assert "比活力" in first_action
    assert "kcat/Km" in first_action
    assert "Tm" in first_action
    assert "热半衰期" in first_action


async def test_mutation_priority_score_returns_specified_mutation_review_tradeoff():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "activity",
            "objective_signals": ["activity", "thermostability"],
            "specified_mutations": ["P338T"],
            "include_lipase_evidence": False,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [86, 114, 275],
            },
            "objective_module_plan": {
                "status": "ready",
                "objective": "specific_activity",
                "objective_signals": ["specific_activity", "thermostability"],
                "multi_objective": True,
                "objective_modules": [
                    {"objective": "specific_activity", "module": "specific_activity"},
                    {"objective": "thermostability", "module": "thermostability"},
                ],
                "candidate_output_allowed": True,
                "missing_evidence": [],
            },
        },
    )

    review = result["specified_mutation_reviews"][0]
    assert review["mutation"] == "P338T"
    assert review["position"] == 338
    assert review["observed_wild_type"] == "P"
    assert review["wild_type_match"] is True
    assert review["review_decision"] == "watch_review"
    assert "activity-stability trade-off" in review["tradeoff_interpretation"]
    assert "Pro->Thr" in review["tradeoff_interpretation"]


async def test_mutation_priority_score_blocks_specified_mutation_numbering_mismatch():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "activity",
            "objective_signals": ["activity"],
            "specified_mutations": ["A338T"],
            "include_lipase_evidence": False,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [86, 114, 275],
            },
            "objective_module_plan": {
                "status": "ready",
                "objective": "specific_activity",
                "objective_signals": ["specific_activity"],
                "candidate_output_allowed": True,
                "missing_evidence": [],
            },
        },
    )

    review = result["specified_mutation_reviews"][0]
    assert review["mutation"] == "A338T"
    assert review["observed_wild_type"] == "P"
    assert review["wild_type_match"] is False
    assert review["review_decision"] == "blocked_numbering_mismatch"
    assert any("wild-type mismatch" in flag for flag in review["risk_flags"])


async def test_mutation_priority_score_blocks_specified_mutation_at_protected_position():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "activity",
            "objective_signals": ["activity"],
            "specified_mutations": ["D86N"],
            "active_site_positions": [86],
            "include_lipase_evidence": False,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [86],
            },
            "objective_module_plan": {
                "status": "ready",
                "objective": "specific_activity",
                "objective_signals": ["specific_activity"],
                "candidate_output_allowed": True,
                "missing_evidence": [],
            },
        },
    )

    review = result["specified_mutation_reviews"][0]
    assert review["mutation"] == "D86N"
    assert review["observed_wild_type"] == "D"
    assert review["wild_type_match"] is True
    assert review["is_protected"] is True
    assert review["review_decision"] == "no_go_protected_position"
    assert "命中催化/功能保护位点，禁止作为首轮候选" in review["risk_flags"]


async def test_mutation_priority_score_projects_site_structure_features_into_rows_and_guardrails():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "activity",
            "objective_signals": ["activity"],
            "site_structure_features": [
                {
                    "position": 338,
                    "wild_type": "P",
                    "pdb_position": "A:338",
                    "is_catalytic": True,
                    "is_protected": True,
                    "b_factor": 18.5,
                    "nearest_catalytic_distance_ca_angstrom": 0.0,
                    "contact_count_ca_8a": 6,
                    "ca_contact_environment": "moderate_ca_neighborhood",
                    "secondary_structure": "helix",
                    "secondary_structure_source": "pdb_helix_sheet_records",
                    "rel_sasa_status": "not_computed",
                    "pocket_channel_interface_status": "not_computed",
                    "nonpolymer_proximity_status": "computed_from_input_pdb",
                    "nearest_nonpolymer_heteroatom_distance_angstrom": 3.2,
                    "nearest_nonpolymer_component_id": "NAG",
                    "nearest_nonpolymer_component_position": "A:201",
                    "nonpolymer_component_ids_within_4a": ["NAG"],
                    "phi_deg": -62.5,
                    "psi_deg": 131.2,
                    "backbone_torsion_status": "computed",
                    "backbone_torsion_reason": None,
                    "backbone_torsion_source": "input_pdb_backbone_atoms_first_model",
                    "risk_flags": ["protected_or_catalytic_position"],
                }
            ],
            "specified_mutations": ["P338T"],
            "include_lipase_evidence": False,
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [],
            },
            "objective_module_plan": {"status": "ready", "candidate_output_allowed": True},
            "objective_module_plan": {
                "status": "ready",
                "objective": "specific_activity",
                "objective_signals": ["specific_activity"],
                "candidate_output_allowed": True,
                "missing_evidence": [],
            },
        },
    )

    row = next(item for item in result["all_positions"] if item["position"] == 338)
    assert row["structure_feature_status"] == "available"
    assert row["ca_b_factor"] == 18.5
    assert row["nearest_catalytic_distance_ca_angstrom"] == 0.0
    assert row["contact_count_ca_8a"] == 6
    assert row["ca_contact_environment"] == "moderate_ca_neighborhood"
    assert row["secondary_structure"] == "helix"
    assert row["rel_sasa_status"] == "not_computed"
    assert row["pocket_channel_interface_status"] == "not_computed"
    assert row["nonpolymer_proximity_status"] == "computed_from_input_pdb"
    assert row["nearest_nonpolymer_heteroatom_distance_angstrom"] == 3.2
    assert row["nearest_nonpolymer_component_id"] == "NAG"
    assert row["nearest_nonpolymer_component_position"] == "A:201"
    assert row["nonpolymer_component_ids_within_4a"] == ["NAG"]
    assert row["phi_deg"] == -62.5
    assert row["psi_deg"] == 131.2
    assert row["backbone_torsion_status"] == "computed"
    assert row["backbone_torsion_source"] == "input_pdb_backbone_atoms_first_model"
    assert row["is_protected"] is True
    assert row["experiment_priority"] == "No-Go"
    assert "protected_or_catalytic_position" in row["risk_flags"]

    review = result["specified_mutation_reviews"][0]
    assert review["review_decision"] == "no_go_protected_position"


async def test_mutation_priority_score_projects_pdb_coordinate_mapping():
    sequence = "A" * 141 + "K" + "A" * 80
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": sequence,
            "engineering_goal": "thermostability",
            "include_lipase_evidence": False,
            "sequence_provenance": "pdb_coordinate_derived",
            "identity_profile": {
                "identity_status": "identified",
                "guardrail": {"status": "ready"},
                "protected_positions": [],
            },
            "objective_module_plan": {"status": "ready", "candidate_output_allowed": True},
            "pdb_coordinate_mapping": [
                {
                    "chain_id": "A",
                    "pdb_residue_no": 142,
                    "coordinate_sequence_position": 142,
                    "residue_aa": "K",
                }
            ],
        },
    )

    candidate = next(row for row in result["all_positions"] if row["position"] == 142)
    assert candidate["pdb_position"] == "A:142"
    assert candidate["numbering_status"] == "pdb_coordinate_derived"


async def test_mutation_priority_score_blocks_without_clear_objective_and_identity():
    result = await ToolRegistry.execute(
        "mutation_priority_score",
        {
            "sequence": _SD_388_SEQUENCE,
            "engineering_goal": "general",
            "include_lipase_evidence": False,
        },
    )

    assert result["identity_gate"]["status"] == "blocked"
    assert result["candidate_table_status"] == "blocked_by_identity_gate"
    assert result["tier_1_candidates"] == []
    assert result["tier_2_candidates"] == []
    assert result["experiment_design_table"] == []
    assert result["candidate_table_boundary"]["evidence_level"] == "blocked"


async def test_rosetta_ddg_blocks_when_runtime_missing(monkeypatch):
    monkeypatch.setattr("app.tools.rosetta_ddg.shutil.which", lambda name: None)
    result = await ToolRegistry.execute(
        "rosetta_ddg",
        {"mutations": ["A10V"], "sequence": "AAAAAAAAAA", "allow_local_estimate": False},
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "ROSETTA_RUNTIME_OR_STRUCTURE_UNAVAILABLE"
    assert result["manual_review_required"] is True
    assert result["thresholds"]["ranges"][0]["label"] == "strong_stabilizing"


async def test_rosetta_ddg_local_estimate_is_labeled_non_rosetta(monkeypatch):
    monkeypatch.setattr("app.tools.rosetta_ddg.shutil.which", lambda name: None)
    monkeypatch.setattr(
        "app.tools.rosetta_ddg._local_estimate",
        lambda sequence, parsed: [
            {"mutation": parsed[0]["mutation"], "wild_type": parsed[0]["wild_type"], "position": parsed[0]["position"], "mutant": parsed[0]["mutant"], "ddg_kcal_mol": -2.5}
        ],
    )
    result = await ToolRegistry.execute(
        "rosetta_ddg",
        {"mutations": ["A10V"], "sequence": "AAAAAAAAAA", "allow_local_estimate": True},
    )

    assert result["status"] == "completed"
    assert result["is_real_rosetta"] is False
    assert result["evidence_level"] == "local_heuristic_estimate"
    assert result["results"][0]["ddg_label"] == "strong_stabilizing"
    assert "non-Rosetta" in result["note"]


async def test_rosetta_ddg_api_call_returns_direct_result(client, session, monkeypatch):
    user = await _create_user(session, "rosetta-ddg-call@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr("app.tools.rosetta_ddg.shutil.which", lambda name: None)
    monkeypatch.setattr(
        "app.tools.rosetta_ddg._local_estimate",
        lambda sequence, parsed: [
            {"mutation": parsed[0]["mutation"], "wild_type": parsed[0]["wild_type"], "position": parsed[0]["position"], "mutant": parsed[0]["mutant"], "ddg_kcal_mol": 1.8}
        ],
    )

    response = await client.post(
        "/api/tools/rosetta_ddg/call",
        json={"params": {"mutations": ["A10V"], "sequence": "AAAAAAAAAA", "allow_local_estimate": True}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["result"]["evidence_level"] == "local_heuristic_estimate"
    assert body["result"]["results"][0]["ddg_label"] == "destabilizing"


async def test_rosetta_ddg_blocks_unmatched_pdb_chain_numbering(monkeypatch):
    monkeypatch.setattr("app.tools.rosetta_ddg.shutil.which", lambda name: None)

    result = await ToolRegistry.execute(
        "rosetta_ddg",
        {
            "mutations": ["A10V"],
            "sequence": "AAAAAAAAAA",
            "pdb_data": _ROSETTA_A10_PDB,
            "chain_id": "B",
        },
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "SEQUENCE_OR_PDB_MUTATION_MISMATCH"
    assert result["chain_id"] == "B"
    assert "Chain 'B'" in result["pdb_validation_errors"][0]["error"]


async def test_rosetta_ddg_real_scorefile_is_parsed_and_classified(monkeypatch):
    monkeypatch.setattr("app.tools.rosetta_ddg._resolve_rosetta_binary", lambda: "/mock/rosetta")

    def fake_run_rosetta_ddg(**kwargs):
        assert kwargs["chain_id"] == "A"
        return {
            "returncode": 0,
            "command": ["/mock/rosetta"],
            "stdout_tail": "",
            "stderr_tail": "",
            "scorefile_exists": True,
            "scorefile_preview": "SCORE: ddg description\nSCORE: -2.4 A10V\n",
        }

    monkeypatch.setattr("app.tools.rosetta_ddg._run_rosetta_ddg", fake_run_rosetta_ddg)

    result = await ToolRegistry.execute(
        "rosetta_ddg",
        {
            "mutations": ["A10V"],
            "sequence": "AAAAAAAAAA",
            "pdb_data": _ROSETTA_A10_PDB,
            "chain_id": "A",
        },
    )

    assert result["status"] == "completed"
    assert result["is_real_rosetta"] is True
    assert result["results"][0]["mutation"] == "A10V"
    assert result["results"][0]["ddg_kcal_mol"] == -2.4
    assert result["results"][0]["ddg_label"] == "strong_stabilizing"
    assert result["scorefile_rows"][0]["description"] == "A10V"


async def test_mutation_epistasis_check_blocks_close_shared_mechanism_pair():
    result = await ToolRegistry.execute(
        "mutation_epistasis_check",
        {
            "mutations": ["A10E", "K12R"],
            "mechanism_tags": {
                "A10E": ["charge_change", "stability_gain"],
                "K12R": ["charge_change", "stability_gain"],
            },
            "structural_distances": {"A10E:K12R": 4.2},
            "same_region_groups": [["A10E", "K12R"]],
            "single_mutant_feedback": {
                "A10E": {"decision": "go"},
                "K12R": {"decision": "go"},
            },
        },
    )

    assert result["status"] == "ok"
    assert result["recommendation"] == "no_go"
    assert result["summary"]["high_risk_pairs"] == 1
    pair = result["pairwise_risks"][0]
    assert pair["risk"] == "high"
    assert pair["distance_source"] == "explicit_pairwise_distance_map"
    assert "same_region_or_pocket" in pair["reasons"]
    assert "repeated_charge_change" in pair["reasons"]
    assert result["report_contract"]["schema_version"] == "mutation_epistasis_check_report_contract_v1"
    assert result["report_contract"]["evidence_inputs"]["structural_distances"] == "provided"
    assert "validated_combination_effect" in result["report_contract"]["must_not_claim"]


async def test_mutation_epistasis_check_allows_orthogonal_validated_pair():
    result = await ToolRegistry.execute(
        "mutation_epistasis_check",
        {
            "mutations": ["A10V", "D80N"],
            "mechanism_tags": {
                "A10V": ["core_packing", "stability_gain"],
                "D80N": ["surface_charge", "activity_gain"],
            },
            "structural_distances": {"A10V:D80N": 22.0},
            "single_mutant_feedback": {
                "A10V": {"decision": "go"},
                "D80N": {"decision": "go"},
            },
        },
    )

    assert result["recommendation"] == "go"
    assert result["summary"]["high_risk_pairs"] == 0
    assert result["pairwise_risks"][0]["reasons"] == ["orthogonal_by_available_evidence"]
    assert result["gradient_experiment_plan"][0]["variant"] == "A10V+D80N"


async def test_mutation_epistasis_check_uses_residue_distance_graph_when_pairwise_map_is_missing():
    result = await ToolRegistry.execute(
        "mutation_epistasis_check",
        {
            "mutations": ["A10V", "D80N"],
            "mechanism_tags": {
                "A10V": ["core_packing", "stability_gain"],
                "D80N": ["surface_charge", "activity_gain"],
            },
            "residue_distance_graph": {
                "schema_version": "residue_distance_graph_v1",
                "status": "ready",
                "coordinate_basis": "ca_atom",
                "radius_angstrom": 8.0,
                "node_count": 2,
                "edge_count": 1,
                "edges": [
                    {
                        "source_position": 10,
                        "target_position": 80,
                        "distance_ca_angstrom": 22.0,
                        "coordinate_basis": "ca_atom",
                        "edge_type": "ca_distance_within_radius",
                    }
                ],
                "boundary": "CA geometry only",
            },
            "single_mutant_feedback": {
                "A10V": {"decision": "go"},
                "D80N": {"decision": "go"},
            },
        },
    )

    assert result["recommendation"] == "go"
    assert result["pairwise_risks"][0]["distance_angstrom"] == 22.0
    assert result["pairwise_risks"][0]["distance_source"] == "residue_distance_graph_v1"
    assert result["summary"]["high_risk_pairs"] == 0
    assert result["report_contract"]["evidence_inputs"]["residue_distance_graph"] == "provided"


async def test_feedback_iteration_planner_does_not_promote_total_activity_as_catalytic_gain():
    result = await ToolRegistry.execute(
        "feedback_iteration_planner",
        {
            "objective": "specific_activity",
            "feedback_records": [
                {
                    "variant_name": "A10V",
                    "mutations": ["A10V"],
                    "assay_payload": {"sample_type": "culture_supernatant"},
                    "metrics_payload": {
                        "total_activity_fold_vs_wt": 1.8,
                        "secreted_expression_pct_wt": 180,
                    },
                    "quality_payload": {"sec_monomer_pct": 95},
                }
            ],
        },
    )

    assert result["status"] == "single_mutant_first"
    assert result["validated_singletons"] == []
    assert result["unresolved_effect_singletons"] == []
    assert result["data_quality"]["effect_disambiguated_records"] == 1
    assert result["planner_mode"] == "constrained_feedback_reweighting_not_trained_epistasis_model"


async def test_feedback_iteration_planner_can_use_residue_distance_graph_for_pair_promotion():
    feedback_records = [
        {
            "variant_name": "A10V",
            "mutations": ["A10V"],
            "assay_payload": {"sample_type": "purified_enzyme"},
            "metrics_payload": {
                "specific_activity_fold_vs_wt": 1.3,
                "activity_retention_pct": 95,
                "tm_delta_c": 0.2,
                "soluble_expression_pct_wt": 100,
            },
            "quality_payload": {"sec_monomer_pct": 95},
        },
        {
            "variant_name": "D80N",
            "mutations": ["D80N"],
            "assay_payload": {"sample_type": "purified_enzyme"},
            "metrics_payload": {
                "specific_activity_fold_vs_wt": 1.25,
                "activity_retention_pct": 93,
                "tm_delta_c": 0.1,
                "soluble_expression_pct_wt": 100,
            },
            "quality_payload": {"sec_monomer_pct": 95},
        },
    ]
    result = await ToolRegistry.execute(
        "feedback_iteration_planner",
        {
            "objective": "specific_activity",
            "feedback_records": feedback_records,
            "mechanism_tags": {
                "A10V": ["core_packing", "activity_gain"],
                "D80N": ["surface_charge", "activity_gain"],
            },
            "residue_distance_graph": {
                "schema_version": "residue_distance_graph_v1",
                "status": "ready",
                "coordinate_basis": "ca_atom",
                "radius_angstrom": 8.0,
                "node_count": 2,
                "edge_count": 1,
                "edges": [
                    {
                        "source_position": 10,
                        "target_position": 80,
                        "distance_ca_angstrom": 22.0,
                        "coordinate_basis": "ca_atom",
                        "edge_type": "ca_distance_within_radius",
                    }
                ],
                "boundary": "CA geometry only",
            },
        },
    )

    assert result["status"] == "ready"
    assert result["structural_distance_source"] == "residue_distance_graph_v1"
    assert result["pair_candidates"][0]["label"] == "validated_singletons_pending_pair_test"
    assert result["next_round_library_design"]["structural_distance_source"] == "residue_distance_graph_v1"
    assert result["next_round_library_design"]["combination_pool"][0]["mutations"] == ["A10V", "D80N"]
    assert result["next_round_library_design"]["combination_pool"][0]["distance_sources"] == ["residue_distance_graph_v1"]
    contract = result["next_round_library_design"]["combination_evidence_contract"]
    assert contract["schema_version"] == "next_round_combination_evidence_contract_v1"
    assert contract["status"] == "ready_with_epistasis_contract"
    assert contract["pair_contracts"][0]["distance_sources"] == ["residue_distance_graph_v1"]
    assert contract["pair_contracts"][0]["evidence_inputs"]["residue_distance_graph"] == "provided"
    assert "validated_combination_effect" in contract["must_not_claim"]


async def test_feedback_iteration_planner_promotes_only_structurally_supported_pair():
    feedback_records = [
        {
            "variant_name": "A10V",
            "mutations": ["A10V"],
            "assay_payload": {"sample_type": "purified_enzyme"},
            "metrics_payload": {
                "specific_activity_fold_vs_wt": 1.3,
                "activity_retention_pct": 95,
                "tm_delta_c": 0.2,
                "soluble_expression_pct_wt": 100,
            },
            "quality_payload": {"sec_monomer_pct": 95},
        },
        {
            "variant_name": "D80N",
            "mutations": ["D80N"],
            "assay_payload": {"sample_type": "purified_enzyme"},
            "metrics_payload": {
                "specific_activity_fold_vs_wt": 1.25,
                "activity_retention_pct": 93,
                "tm_delta_c": 0.1,
                "soluble_expression_pct_wt": 100,
            },
            "quality_payload": {"sec_monomer_pct": 95},
        },
    ]
    result = await ToolRegistry.execute(
        "feedback_iteration_planner",
        {
            "objective": "specific_activity",
            "feedback_records": feedback_records,
            "mechanism_tags": {
                "A10V": ["core_packing", "activity_gain"],
                "D80N": ["surface_charge", "activity_gain"],
            },
            "structural_distances": {"A10V:D80N": 22.0},
        },
    )

    assert result["status"] == "ready"
    assert len(result["validated_singletons"]) == 2
    assert result["pair_candidates"][0]["label"] == "validated_singletons_pending_pair_test"
    assert result["exploration_policy"]["explore_fraction"] == 0.3
    library = result["next_round_library_design"]
    assert library["schema_version"] == "next_round_library_design_v1"
    assert library["status"] == "ready_for_controlled_pair_library"
    assert library["combination_pool"][0]["mutations"] == ["A10V", "D80N"]
    assert library["higher_order_rule"]["status"] == "blocked"
    assert library["plate_layout"][0]["well_group"] == "controls"
    assert any(item["well_group"] == "controlled_pairs" for item in library["plate_layout"])


async def test_feedback_iteration_planner_blocks_remote_noise_without_mechanistic_evidence():
    result = await ToolRegistry.execute(
        "feedback_iteration_planner",
        {
            "feedback_records": [
                {
                    "variant_name": "A10V",
                    "mutations": ["A10V"],
                    "assay_payload": {"sample_type": "purified_enzyme"},
                    "metrics_payload": {"specific_activity_fold_vs_wt": 1.3, "activity_retention_pct": 90},
                    "quality_payload": {"sec_monomer_pct": 95},
                }
            ],
            "remote_candidates": [{"mutation": "K200Q"}],
        },
    )

    assert result["remote_exploration"][0]["state"] == "insufficient_evidence_not_promoted"
    assert "structural_connectivity_or_real_md_artifact" in result["remote_exploration"][0]["required_evidence"]
    library = result["next_round_library_design"]
    assert library["status"] == "singletons_only_extend_validation"
    assert library["exploration_pool"] == []
    assert library["combination_pool"] == []


async def test_residue_numbering_gate_requires_mapping_and_confirmation():
    missing_mapping = await ToolRegistry.execute(
        "residue_numbering_gate",
        {"requested_positions": [223], "sequence_length": 388, "pdb_id": "1TST", "chain_id": "A"},
    )
    unconfirmed = await ToolRegistry.execute(
        "residue_numbering_gate",
        {
            "requested_positions": [223],
            "mapping_rows": [
                {
                    "source_scheme": "user_sequence",
                    "source_position": 223,
                    "target_scheme": "pdb",
                    "target_position": 204,
                    "confidence": "sifts",
                    "method": "local_sifts",
                }
            ],
            "user_confirmed": False,
        },
    )
    allowed = await ToolRegistry.execute(
        "residue_numbering_gate",
        {
            "requested_positions": [223],
            "mapping_rows": [
                {
                    "source_scheme": "user_sequence",
                    "source_position": 223,
                    "target_scheme": "pdb",
                    "target_position": 204,
                    "confidence": "sifts",
                    "method": "local_sifts",
                }
            ],
            "user_confirmed": True,
        },
    )

    assert missing_mapping["status"] == "blocked"
    assert missing_mapping["blocked_reason"] == "missing_numbering_mapping"
    assert unconfirmed["status"] == "blocked"
    assert unconfirmed["blocked_reason"] == "mapping_conflicts_or_unconfirmed"
    assert allowed["status"] == "allowed"
    assert allowed["numbering_schema"] == "unified_numbering_registry_v1"
    assert allowed["allowed_operations"]["automatic_combination_design"] is True


async def test_residue_numbering_gate_accepts_unified_numbering_registry_rows():
    blocked = await ToolRegistry.execute(
        "residue_numbering_gate",
        {
            "requested_positions": [223],
            "mapping_rows": [
                {
                    "source_scheme": "user_sequence",
                    "source_position": 223,
                    "target_scheme": "pdb_author",
                    "target_position": 204,
                    "target_chain_id": "A",
                    "target_insertion_code": None,
                    "coordinate_system": "pdb_author_residue_number",
                    "mapping_scope": "chain",
                    "gap_status": "present",
                    "confidence": "inferred",
                    "method": "local_sifts_style_inference",
                }
            ],
            "user_confirmed": False,
        },
    )
    warning = await ToolRegistry.execute(
        "residue_numbering_gate",
        {
            "requested_positions": [223],
            "mapping_rows": [
                {
                    "source_scheme": "user_sequence",
                    "source_position": 223,
                    "target_scheme": "pdb_author",
                    "target_position": 204,
                    "target_chain_id": "A",
                    "target_insertion_code": None,
                    "coordinate_system": "pdb_author_residue_number",
                    "mapping_scope": "chain",
                    "gap_status": "present",
                    "confidence": "inferred",
                    "method": "local_sifts_style_inference",
                }
            ],
            "user_confirmed": True,
        },
    )

    assert blocked["status"] == "blocked"
    assert blocked["blocked_reason"] == "mapping_conflicts_or_unconfirmed"
    assert "low_or_unknown_mapping_confidence" in blocked["limitations"]
    assert warning["status"] == "warning"
    assert warning["numbering_schema"] == "unified_numbering_registry_v1"
    assert warning["mapped_positions"][0]["target_scheme"] == "pdb_author"


async def test_ligand_preprocess_stage_contract_reports_missing_parameters(monkeypatch):
    monkeypatch.setattr("app.tools.ligand_preprocess.shutil.which", lambda name: None)

    result = await ToolRegistry.execute(
        "ligand_preprocess",
        {
            "sdf_data": _LIGAND_2D_SDF,
            "stages": ["prepare_pdbqt", "vina_docking", "ligand_topology"],
            "store_outputs": False,
        },
    )

    assert result["status"] == "blocked"
    by_stage = {item["stage"]: item for item in result["stage_results"]}
    assert by_stage["prepare_pdbqt"]["blocked_reason"] == "missing_parameters"
    assert "ligand_3d input" in by_stage["prepare_pdbqt"]["missing_parameters"]
    assert by_stage["vina_docking"]["blocked_reason"] == "missing_parameters"
    assert "receptor_pdbqt input" in by_stage["vina_docking"]["missing_parameters"]
    assert "pocket_center" in by_stage["vina_docking"]["missing_parameters"]
    assert by_stage["ligand_topology"]["blocked_reason"] == "missing_parameters"
    assert "ligand_3d input" in by_stage["ligand_topology"]["missing_parameters"]
    assert result["stage_readiness"]["blocked"] == ["prepare_pdbqt", "vina_docking", "ligand_topology"]
    assert result["stage_readiness"]["can_enter_docking"] is False
    assert result["stage_readiness"]["can_enter_gromacs_complex_md"] is False
    assert "prepare_pdbqt" in result["stage_contract"]["required_parameters"]
    assert result["stage_contract"]["parameters"]["charge_model"] == "gasteiger"


async def test_ligand_preprocess_rejects_malformed_sdf_without_exception():
    result = await ToolRegistry.execute(
        "ligand_preprocess",
        {
            "sdf_data": "bad\n  test\n\n  x V2000\nM  END\n$$$$\n",
            "stages": ["preflight", "generate_3d"],
            "store_outputs": False,
        },
    )

    assert result["status"] == "blocked"
    assert result["blocked_reason"] == "invalid_or_unsupported_sdf"
    assert result["sdf"]["parse_status"] == "unsupported"


async def test_ligand_preprocess_pipeline_feeds_generated_pdbqt_into_vina(monkeypatch):
    monkeypatch.setattr(
        "app.tools.ligand_preprocess.shutil.which",
        lambda name: f"/mock/bin/{name}" if name in {"obabel", "vina"} else None,
    )

    def fake_run_command(command, cwd, timeout_seconds):
        del timeout_seconds
        if "--gen3d" in command:
            (cwd / "ligand_3d.sdf").write_text(_LIGAND_3D_SDF, encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="generated", stderr="")
        if "--out" in command:
            output_path = cwd / "docked_poses.pdbqt"
            output_path.write_text("REMARK VINA RESULT\nMODEL 1\nENDMDL\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="mode affinity\n1 -5.0\n", stderr="")
        if "ligand.pdbqt" in " ".join(command):
            (cwd / "ligand.pdbqt").write_text("REMARK ligand pdbqt\nATOM      1  C   LIG     1       0.000   0.000   0.000\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="prepared", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

    monkeypatch.setattr("app.tools.ligand_preprocess._run_command", fake_run_command)

    result = await ToolRegistry.execute(
        "ligand_preprocess",
        {
            "sdf_data": _LIGAND_2D_SDF,
            "stages": ["generate_3d", "prepare_pdbqt", "vina_docking"],
            "receptor_pdbqt_data": "REMARK receptor pdbqt\nATOM      1  C   REC     1       0.000   0.000   0.000\n",
            "pocket_center": {"x": 0, "y": 0, "z": 0},
            "pocket_size": {"x": 10, "y": 10, "z": 10},
            "store_outputs": False,
        },
    )

    assert result["status"] == "completed"
    assert [item["status"] for item in result["stage_results"]] == ["completed", "completed", "completed"]
    assert result["stage_results"][1]["output_pdbqt"]["included"] is True
    assert "VINA RESULT" in result["stage_results"][2]["output_pdbqt"]["text"]
    assert all("_pipeline_sdf_text" not in item and "_pipeline_pdbqt_text" not in item for item in result["stage_results"])
    assert result["stage_readiness"]["can_enter_docking"] is True


async def test_ligand_preprocess_vina_box_requires_all_axes(monkeypatch):
    monkeypatch.setattr(
        "app.tools.ligand_preprocess.shutil.which",
        lambda name: f"/mock/bin/{name}" if name == "vina" else None,
    )

    result = await ToolRegistry.execute(
        "ligand_preprocess",
        {
            "sdf_data": _LIGAND_2D_SDF,
            "stages": ["vina_docking"],
            "ligand_pdbqt_data": "REMARK ligand\n",
            "receptor_pdbqt_data": "REMARK receptor\n",
            "pocket_center": {"x": 0, "y": 0},
            "pocket_size": {"x": 10, "y": -1, "z": 10},
            "store_outputs": False,
        },
    )

    vina = result["stage_results"][0]
    assert result["status"] == "blocked"
    assert vina["stage"] == "vina_docking"
    assert vina["blocked_reason"] == "missing_parameters"
    assert "pocket_center.z" in vina["missing_parameters"]
    assert "pocket_size.y_positive" in vina["missing_parameters"]


async def test_ligand_preprocess_topology_reports_real_acpype_failure(monkeypatch):
    monkeypatch.setattr(
        "app.tools.ligand_preprocess.shutil.which",
        lambda name: f"/mock/bin/{name}" if name in {"obabel", "acpype"} else None,
    )

    def fake_run_command(command, cwd, timeout_seconds):
        del timeout_seconds
        if "ligand.mol2" in " ".join(command) and "--partialcharge" in command:
            (cwd / "ligand.mol2").write_text("@<TRIPOS>MOLECULE\nligand\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="mol2 ok", stderr="")
        if "-b" in command and "ligand" in command:
            assert "-a" in command
            assert "gaff2" in command
            assert "-o" in command
            assert "gmx" in command
            return SimpleNamespace(returncode=1, stdout="", stderr="ACPYPE backend failed")
        return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

    monkeypatch.setattr("app.tools.ligand_preprocess._run_command", fake_run_command)

    result = await ToolRegistry.execute(
        "ligand_preprocess",
        {
            "sdf_data": _LIGAND_2D_SDF,
            "stages": ["ligand_topology"],
            "ligand_3d_data": _LIGAND_3D_SDF,
            "net_charge": 0,
            "ligand_force_field": "gaff2",
            "store_outputs": False,
        },
    )

    topology = result["stage_results"][0]
    assert result["status"] == "failed"
    assert topology["stage"] == "ligand_topology"
    assert topology["status"] == "failed"
    assert topology["returncode"] == 1
    assert "ACPYPE backend failed" in topology["error"]
    assert result["stage_readiness"]["failed"] == ["ligand_topology"]


async def test_ligand_preprocess_antechamber_only_does_not_mark_topology_ready(monkeypatch):
    monkeypatch.setattr(
        "app.tools.ligand_preprocess.shutil.which",
        lambda name: f"/mock/bin/{name}" if name in {"obabel", "antechamber"} else None,
    )
    monkeypatch.setattr("app.tools.ligand_preprocess.Path.exists", lambda self: False)

    result = await ToolRegistry.execute(
        "ligand_preprocess",
        {
            "sdf_data": _LIGAND_2D_SDF,
            "stages": ["preflight", "ligand_topology"],
            "ligand_3d_data": _LIGAND_3D_SDF,
            "store_outputs": False,
        },
    )

    by_stage = {item["stage"]: item for item in result["stage_results"]}
    assert by_stage["preflight"]["status"] == "blocked"
    assert "ligand_topology" in by_stage["preflight"]["missing_requirements"]
    assert by_stage["ligand_topology"]["blocked_reason"] == "ligand_topology_runtime_not_available"
    assert by_stage["ligand_topology"]["required_tools"] == ["acpype", "AmberTools"]


async def test_ligand_preprocess_command_timeout_is_structured(monkeypatch):
    monkeypatch.setattr(
        "app.tools.ligand_preprocess.shutil.which",
        lambda name: f"/mock/bin/{name}" if name == "obabel" else None,
    )

    def fake_run_command(command, cwd, timeout_seconds):
        del command, cwd, timeout_seconds
        return SimpleNamespace(returncode=124, stdout="", stderr="Command timed out after 1 seconds")

    monkeypatch.setattr("app.tools.ligand_preprocess._run_command", fake_run_command)

    result = await ToolRegistry.execute(
        "ligand_preprocess",
        {
            "sdf_data": _LIGAND_2D_SDF,
            "stages": ["prepare_pdbqt"],
            "ligand_3d_data": _LIGAND_3D_SDF,
            "store_outputs": False,
            "timeout_seconds": 1,
        },
    )

    stage = result["stage_results"][0]
    assert result["status"] == "failed"
    assert stage["status"] == "failed"
    assert stage["failed_reason"] == "command_timeout"
    assert "timed out" in stage["error"]


def test_ligand_stage_readiness_requires_executed_topology_artifacts():
    from app.tools.ligand_preprocess import _stage_readiness

    capability_only = _stage_readiness([{
        "stage": "ligand_topology",
        "status": "completed",
        "artifact_count": 1,
        "evidence_level": "runtime_capability_only",
    }])
    assert capability_only["can_enter_gromacs_complex_md"] is False
    assert capability_only["gromacs_complex_md_blocked_reason"] == "topology_evidence_incomplete"

    executed = _stage_readiness([{
        "stage": "ligand_topology",
        "status": "completed",
        "artifact_count": 3,
        "topology_artifact_names": ["ligand_GMX.itp", "ligand_GMX.top", "ligand_GMX.gro"],
        "topology_artifact_manifest": [
            {"name": "ligand_GMX.itp", "size": 10, "sha256": "a" * 64},
            {"name": "ligand_GMX.top", "size": 10, "sha256": "b" * 64},
            {"name": "ligand_GMX.gro", "size": 10, "sha256": "c" * 64},
        ],
        "evidence_level": "executed_topology_artifacts",
    }])
    assert executed["can_enter_gromacs_complex_md"] is True
    assert executed["gromacs_complex_md_blocked_reason"] is None


async def test_ligand_preprocess_api_call_rejects_async_execution(client, session, monkeypatch):
    user = await _create_user(session, "ligand-preprocess-call@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    response = await client.post(
        "/api/tools/ligand_preprocess/call",
        json={"params": {"sdf_data": _LIGAND_2D_SDF, "stages": ["preflight", "prepare_pdbqt"]}},
    )

    assert response.status_code == 400
    assert "async-only" in response.json()["detail"]


async def test_ligand_preprocess_submit_rejects_unowned_object_and_local_path(client, session, monkeypatch):
    user = await _create_user(session, "ligand-preprocess-unowned@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    dispatched: list[tuple[str, dict]] = []
    monkeypatch.setattr("app.api.tools.dispatch_tool", lambda tool_name, params: dispatched.append((tool_name, params)) or "unexpected")

    local_path_resp = await client.post(
        "/api/tools/ligand_preprocess/submit",
        json={"params": {"sdf_path": "../Structure2D_COMPOUND_CID_5478883.sdf", "stages": ["preflight"]}},
    )
    unowned_resp = await client.post(
        "/api/tools/ligand_preprocess/submit",
        json={"params": {"sdf_object_name": "uploads/user_999/ligand.sdf", "stages": ["preflight"]}},
    )

    assert local_path_resp.status_code == 400
    assert "not accepted through the HTTP API" in local_path_resp.json()["detail"]
    assert unowned_resp.status_code == 403
    assert dispatched == []


async def test_ligand_preprocess_submit_creates_ligand_cpu_audit(client, session, monkeypatch):
    user = await _create_user(session, "ligand-preprocess-submit@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr("app.api.tools.dispatch_tool", lambda tool_name, params: "ligand-preprocess-task-id")

    response = await client.post(
        "/api/tools/ligand_preprocess/submit",
        json={"params": {"sdf_object_name": f"uploads/user_{user.id}/ligand.sdf", "stages": ["preflight"]}},
    )
    audit_response = await client.get("/api/tools/tasks/ligand-preprocess-task-id/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == "ligand_preprocess"
    assert body["queue"] == "ligand_cpu"
    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["tool"] == "ligand_preprocess"
    assert audit["queue"] == "ligand_cpu"
    assert audit["input_summary"]["values"]["sdf_object_name"] == f"uploads/user_{user.id}/ligand.sdf"


async def test_ligand_task_polling_records_artifact_owner_for_download(client, session, monkeypatch):
    user = await _create_user(session, "ligand-artifact-owner@example.com")
    await session.commit()
    await record_tool_task_owner("ligand-artifact-task-id", user.id, "ligand_preprocess")
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "completed",
            "result": {
                "status": "completed",
                "tool": "ligand_preprocess",
                "result": {
                    "job_id": "ligand-job",
                    "artifacts": [
                        {
                            "name": "ligand_3d.sdf",
                            "object_name": "ligands/ligand-job/ligand_3d.sdf",
                            "download_url": "/api/files/ligands/ligand-job/ligand_3d.sdf/download",
                            "category": "structures",
                        }
                    ],
                    "artifact_manifest": {
                        "version": 1,
                        "total_count": 1,
                        "groups": {
                            "structures": [{"name": "ligand_3d.sdf", "object_name": "ligands/ligand-job/ligand_3d.sdf"}],
                        },
                    },
                },
            },
            "error": None,
            "progress": 100,
        },
    )

    response = await client.get("/api/tools/tasks/ligand-artifact-task-id")

    assert response.status_code == 200
    owner = await get_tool_artifact_owner("ligands/ligand-job/ligand_3d.sdf")
    assert owner is not None
    assert owner["user_id"] == user.id
    assert owner["tool_name"] == "ligand_preprocess"


async def test_md_replicate_batch_submit_dry_run_does_not_dispatch(client, session, monkeypatch):
    user = await _create_user(session, "tool-md-batch-plan@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    dispatched: list[tuple[str, dict]] = []
    monkeypatch.setattr("app.api.tools.dispatch_tool", lambda tool_name, params: dispatched.append((tool_name, params)) or "unexpected")

    response = await client.post(
        "/api/tools/md/replicates/submit",
        json={
            "protocol_id": "engineering_short",
            "pdb_object_name": "uploads/user/wt.pdb",
            "replicate_count": 2,
            "replicate_variants": ["M204H"],
            "dry_run": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "planned"
    assert body["dry_run"] is True
    assert body["submittable_count"] == 2
    assert body["blocked_count"] == 2
    assert body["blocked_tasks"][0]["reason"] == "missing_prepared_mutant_structure"
    assert body["confirmation_required"] == "SUBMIT_MD_REPLICATES"
    assert dispatched == []


async def test_md_replicate_batch_submit_records_wt_tasks_and_blocks_missing_mutants(client, session, monkeypatch):
    user = await _create_user(session, "tool-md-batch-submit@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    dispatched: list[tuple[str, dict]] = []

    def fake_dispatch(tool_name, params):
        dispatched.append((tool_name, params))
        return f"md-replicate-task-{len(dispatched)}"

    monkeypatch.setattr("app.api.tools.dispatch_tool", fake_dispatch)

    response = await client.post(
        "/api/tools/md/replicates/submit",
        json={
            "protocol_id": "engineering_short",
            "pdb_object_name": "uploads/user/wt.pdb",
            "replicate_count": 2,
            "replicate_seed_base": 7000,
            "replicate_variants": ["M204H"],
            "dry_run": False,
            "confirmation": "SUBMIT_MD_REPLICATES",
        },
    )
    audit_response = await client.get("/api/tools/tasks/md-replicate-task-1/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partially_submitted"
    assert body["submitted_count"] == 2
    assert body["blocked_count"] == 2
    assert [item["task_id"] for item in body["submitted_tasks"]] == ["md-replicate-task-1", "md-replicate-task-2"]
    assert [item["seed"] for item in body["submitted_tasks"]] == [7001, 7002]
    assert all(item["queue"] == "md_cpu" for item in body["submitted_tasks"])
    assert dispatched[0][0] == "gromacs_md"
    assert dispatched[0][1]["run_seed"] == 7001
    assert dispatched[0][1]["replicate_variant"] == "WT"
    assert dispatched[0][1]["replicate_index"] == 1
    assert dispatched[0][1]["pdb_object_name"] == "uploads/user/wt.pdb"
    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["tool"] == "gromacs_md"
    assert audit["status"] == "submitted"
    assert audit["input_summary"]["values"]["run_seed"] == 7001
    assert audit["input_summary"]["values"]["replicate_variant"] == "WT"


async def test_md_replicate_batch_submit_can_require_mutant_topology_validation(client, session, monkeypatch):
    user = await _create_user(session, "tool-md-batch-submit-topology@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    dispatched: list[tuple[str, dict]] = []

    def fake_dispatch(tool_name, params):
        dispatched.append((tool_name, params))
        return f"md-topology-gated-task-{len(dispatched)}"

    monkeypatch.setattr("app.api.tools.dispatch_tool", fake_dispatch)

    blocked_response = await client.post(
        "/api/tools/md/replicates/submit",
        json={
            "protocol_id": "engineering_short",
            "pdb_object_name": "uploads/user/wt.pdb",
            "replicate_count": 1,
            "replicate_variants": ["M204A"],
            "mutant_inputs": {"M204A": {"pdb_object_name": "md-mutants/m204a.pdb"}},
            "require_mutant_topology_validation": True,
            "dry_run": True,
        },
    )
    validated_response = await client.post(
        "/api/tools/md/replicates/submit",
        json={
            "protocol_id": "engineering_short",
            "pdb_object_name": "uploads/user/wt.pdb",
            "replicate_count": 1,
            "replicate_variants": ["M204A"],
            "mutant_inputs": {
                "M204A": {
                    "pdb_object_name": "md-mutants/m204a.pdb",
                    "topology_validation": {"topology_validated": True, "safe_for_ranking": True},
                }
            },
            "require_mutant_topology_validation": True,
            "dry_run": True,
        },
    )

    assert blocked_response.status_code == 200
    blocked_body = blocked_response.json()
    assert blocked_body["submittable_count"] == 1
    assert blocked_body["blocked_count"] == 1
    assert blocked_body["blocked_tasks"][0]["reason"] == "mutant_topology_not_validated"
    assert validated_response.status_code == 200
    validated_body = validated_response.json()
    assert validated_body["submittable_count"] == 2
    assert validated_body["blocked_count"] == 0
    assert {item["variant"] for item in validated_body["submittable_tasks"]} == {"WT", "M204A"}
    assert dispatched == []


async def test_md_mutant_prepare_returns_inline_mutant_input(client, session):
    user = await _create_user(session, "tool-md-mutant-prepare@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.post(
        "/api/tools/md/mutants/prepare",
        json={"pdb_data": _MUTANT_PREPARE_PDB, "variants": ["A:M204A"], "store": False},
    )

    assert response.status_code == 200
    body = response.json()
    mutant = body["mutants"][0]
    assert body["status"] == "prepared"
    assert body["topology_policy"]["requires_gromacs_pdb2gmx_validation"] is True
    assert mutant["status"] == "prepared"
    assert mutant["topology_readiness"] == "requires_topology_validation"
    assert mutant["mutant_input"]["pdb_data"] == mutant["pdb_data"]
    assert "ALA A 204" in mutant["mutant_input"]["pdb_data"]
    assert " SD  ALA" not in mutant["mutant_input"]["pdb_data"]
    assert body["store"] == {"enabled": False, "stored_count": 0}


async def test_md_mutant_prepare_can_attach_topology_validation(client, session, monkeypatch):
    user = await _create_user(session, "tool-md-mutant-prepare-validate@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    def fake_validate(pdb_text: str, *, force_field: str, water_model: str, timeout: int):
        assert "ALA A 204" in pdb_text
        assert force_field == "amber99sb-ildn"
        assert water_model == "tip3p"
        assert timeout == 45
        return {"status": "validated", "topology_validated": True, "safe_for_ranking": True}

    monkeypatch.setattr("app.tools.gromacs_md._validate_pdb_topology", fake_validate)

    response = await client.post(
        "/api/tools/md/mutants/prepare",
        json={
            "pdb_data": _MUTANT_PREPARE_PDB,
            "variants": ["A:M204A"],
            "validate_topology": True,
            "topology_timeout_seconds": 45,
        },
    )

    assert response.status_code == 200
    body = response.json()
    mutant = body["mutants"][0]
    assert body["topology_validation"]["enabled"] is True
    assert body["topology_validation"]["safe_count"] == 1
    assert mutant["topology_readiness"] == "validated_for_replicate_submit"
    assert mutant["topology_validation"]["safe_for_ranking"] is True
    assert mutant["mutant_input"]["topology_validation"]["topology_validated"] is True


async def test_md_mutant_prepare_can_store_generated_pdb_for_replicate_submit(client, session, monkeypatch):
    user = await _create_user(session, "tool-md-mutant-prepare-store@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    uploads: list[dict] = []

    async def fake_upload_file(data: bytes, filename: str, content_type: str, folder: str):
        uploads.append({"data": data, "filename": filename, "content_type": content_type, "folder": folder})
        return {
            "object_name": "md-mutants/generated-mutant.pdb",
            "bucket": "local",
            "size": len(data),
            "download_url": "/api/files/md-mutants/generated-mutant.pdb/download",
            "storage": "local",
        }

    monkeypatch.setattr("app.api.tools.storage.upload_file", fake_upload_file)

    response = await client.post(
        "/api/tools/md/mutants/prepare",
        json={"pdb_data": _MUTANT_PREPARE_PDB, "variants": ["A:M204A"], "store": True},
    )

    assert response.status_code == 200
    body = response.json()
    mutant = body["mutants"][0]
    assert body["store"] == {"enabled": True, "stored_count": 1}
    assert mutant["mutant_input"] == {"pdb_object_name": "md-mutants/generated-mutant.pdb"}
    assert mutant["stored"]["object_name"] == "md-mutants/generated-mutant.pdb"
    assert "pdb_data" not in mutant
    assert uploads[0]["filename"] == "A:M204A.pdb"
    assert uploads[0]["content_type"] == "chemical/x-pdb"
    assert uploads[0]["folder"] == "md-mutants"
    assert b"ALA A 204" in uploads[0]["data"]


async def test_md_mutant_prepare_blocks_ambiguous_chain(client, session):
    user = await _create_user(session, "tool-md-mutant-prepare-ambiguous@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))
    pdb = _MUTANT_PREPARE_PDB.replace(" A 204", " B 204") + _MUTANT_PREPARE_PDB

    response = await client.post(
        "/api/tools/md/mutants/prepare",
        json={"pdb_data": pdb, "variants": ["M204A"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked_or_partial"
    assert body["mutants"][0]["status"] == "blocked"
    assert body["mutants"][0]["blocked_reason"] == "ambiguous_residue_without_chain"


async def test_md_topology_validate_endpoint_returns_real_precheck_contract(client, session, monkeypatch):
    user = await _create_user(session, "tool-md-topology-validate@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    def fake_validate(pdb_text: str, *, force_field: str, water_model: str, timeout: int):
        assert "MET A 204" in pdb_text
        assert force_field == "amber99sb-ildn"
        assert water_model == "tip3p"
        assert timeout == 30
        return {
            "version": 1,
            "status": "validated",
            "topology_validated": True,
            "safe_for_ranking": True,
            "outputs": {"processed_gro": True, "topol_top": True},
            "topology_review": {"warning_count": 0, "risk_flags": [], "warnings": [], "entries": []},
        }

    monkeypatch.setattr("app.tools.gromacs_md._validate_pdb_topology", fake_validate)

    response = await client.post(
        "/api/tools/md/topology/validate",
        json={
            "pdb_data": _MUTANT_PREPARE_PDB,
            "force_field": "amber99sb-ildn",
            "water_model": "tip3p",
            "timeout_seconds": 30,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated"
    assert body["topology_validated"] is True
    assert body["safe_for_ranking"] is True
    assert body["requested_by_user_id"] == user.id
    assert "Topology precheck passed" in body["next_steps"][0]


def _md_replicate_audit(
    *,
    task_id: str,
    user_id: int,
    batch_id: str,
    variant: str,
    replicate_index: int,
    run_seed: int,
    rmsd_drift_nm: float | None,
    mean_rmsf_nm: float | None,
    rg_change_nm: float | None,
    sasa_change_nm2: float | None,
    status: str = "completed",
) -> ToolTaskAudit:
    md_replicate = {
        "batch_id": batch_id,
        "replicate_variant": variant,
        "replicate_index": replicate_index,
        "run_seed": run_seed,
        "rmsd_drift_nm": rmsd_drift_nm,
        "mean_rmsf_nm": mean_rmsf_nm,
        "rg_change_nm": rg_change_nm,
        "sasa_change_nm2": sasa_change_nm2,
        "is_stable": bool(rmsd_drift_nm is not None and abs(rmsd_drift_nm) < 0.15),
    }
    return ToolTaskAudit(
        task_id=task_id,
        user_id=user_id,
        tool_name="gromacs_md",
        status=status,
        queue="md_cpu",
        input_summary={
            "keys": ["batch_id", "replicate_variant", "replicate_index", "run_seed"],
            "values": {
                "batch_id": batch_id,
                "replicate_variant": variant,
                "replicate_index": replicate_index,
                "run_seed": run_seed,
            },
        },
        result_summary={
            "status": status,
            "job_id": f"job-{task_id}",
            "is_real_md": True,
            "engine": "GROMACS",
            "artifact_count": 4,
            "has_artifact_manifest": True,
            "md_replicate": md_replicate,
        },
        submitted_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10),
        terminal_recorded_at=datetime.now(timezone.utc).replace(tzinfo=None) if status == "completed" else None,
    )


async def test_md_replicate_batch_summary_ranks_completed_current_user_tasks(client, session):
    user = await _create_user(session, "tool-md-batch-summary@example.com")
    other = await _create_user(session, "tool-md-batch-summary-other@example.com")
    batch_id = "mdrep_summary_ready"
    session.add_all(
        [
            _md_replicate_audit(
                task_id="summary-wt-1",
                user_id=user.id,
                batch_id=batch_id,
                variant="WT",
                replicate_index=1,
                run_seed=1001,
                rmsd_drift_nm=0.10,
                mean_rmsf_nm=0.20,
                rg_change_nm=0.01,
                sasa_change_nm2=1.0,
            ),
            _md_replicate_audit(
                task_id="summary-wt-2",
                user_id=user.id,
                batch_id=batch_id,
                variant="WT",
                replicate_index=2,
                run_seed=1002,
                rmsd_drift_nm=0.11,
                mean_rmsf_nm=0.21,
                rg_change_nm=0.02,
                sasa_change_nm2=1.1,
            ),
            _md_replicate_audit(
                task_id="summary-mut-1",
                user_id=user.id,
                batch_id=batch_id,
                variant="M204H",
                replicate_index=1,
                run_seed=2001,
                rmsd_drift_nm=0.08,
                mean_rmsf_nm=0.18,
                rg_change_nm=0.0,
                sasa_change_nm2=0.5,
            ),
            _md_replicate_audit(
                task_id="summary-mut-2",
                user_id=user.id,
                batch_id=batch_id,
                variant="M204H",
                replicate_index=2,
                run_seed=2002,
                rmsd_drift_nm=0.09,
                mean_rmsf_nm=0.19,
                rg_change_nm=0.0,
                sasa_change_nm2=0.4,
            ),
            _md_replicate_audit(
                task_id="summary-other-user",
                user_id=other.id,
                batch_id=batch_id,
                variant="WT",
                replicate_index=1,
                run_seed=9001,
                rmsd_drift_nm=0.50,
                mean_rmsf_nm=0.50,
                rg_change_nm=0.50,
                sasa_change_nm2=5.0,
            ),
        ]
    )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get(f"/api/tools/md/replicates/{batch_id}/summary", params={"minimum_replicates": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ranking_ready"
    assert body["task_count"] == 4
    assert body["completed_count"] == 4
    assert body["pending_count"] == 0
    assert body["failed_count"] == 0
    assert body["blocked_reason"] is None
    assert len(body["wild_type_replicates"]) == 2
    assert len(body["mutant_replicates"]) == 2
    assert body["mutant_replicates"][0]["delta_reference"] == "wt_batch_mean"
    assert body["batch_replicate_summary"]["ranking_allowed"] is True
    assert body["batch_replicate_summary"]["ranked_candidates"][0]["variant"] == "M204H"
    assert all(audit["task_id"] != "summary-other-user" for audit in body["audits"])


async def test_md_replicate_batch_summary_blocks_pending_or_missing_metrics(client, session):
    user = await _create_user(session, "tool-md-batch-summary-blocked@example.com")
    batch_id = "mdrep_summary_blocked"
    session.add_all(
        [
            _md_replicate_audit(
                task_id="summary-blocked-wt",
                user_id=user.id,
                batch_id=batch_id,
                variant="WT",
                replicate_index=1,
                run_seed=1001,
                rmsd_drift_nm=0.10,
                mean_rmsf_nm=None,
                rg_change_nm=0.01,
                sasa_change_nm2=1.0,
            ),
            _md_replicate_audit(
                task_id="summary-blocked-pending",
                user_id=user.id,
                batch_id=batch_id,
                variant="WT",
                replicate_index=2,
                run_seed=1002,
                rmsd_drift_nm=0.11,
                mean_rmsf_nm=0.21,
                rg_change_nm=0.02,
                sasa_change_nm2=1.1,
                status="running",
            ),
        ]
    )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get(f"/api/tools/md/replicates/{batch_id}/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "incomplete"
    assert body["pending_count"] == 1
    assert body["blocked_reason"] == "tasks_not_terminal"
    assert body["missing_metrics"] == [{"task_id": "summary-blocked-wt", "missing": ["mean_rmsf_nm"]}]
    assert body["next_steps"] == ["Wait for all submitted replicate tasks to reach a terminal state."]


async def test_md_replicate_batch_summary_hides_other_user_batch(client, session):
    owner = await _create_user(session, "tool-md-batch-summary-owner@example.com")
    intruder = await _create_user(session, "tool-md-batch-summary-intruder@example.com")
    batch_id = "mdrep_summary_private"
    session.add(
        _md_replicate_audit(
            task_id="summary-private-wt",
            user_id=owner.id,
            batch_id=batch_id,
            variant="WT",
            replicate_index=1,
            run_seed=1001,
            rmsd_drift_nm=0.10,
            mean_rmsf_nm=0.20,
            rg_change_nm=0.01,
            sasa_change_nm2=1.0,
        )
    )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(intruder.id))

    response = await client.get(f"/api/tools/md/replicates/{batch_id}/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_tasks"
    assert body["task_count"] == 0
    assert body["audits"] == []


async def test_tool_task_polling_updates_persistent_audit(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-audit-poll@example.com")
    await session.commit()
    await record_tool_task_owner("audit-poll-task-id", user.id, "gromacs_md")
    await record_tool_task_runtime_policy("audit-poll-task-id", queue="md_cpu", soft_time_limit=3600, time_limit=5400)
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "completed",
            "result": {
                "status": "completed",
                "tool": "gromacs_md",
                "result": {
                    "job_id": "job-audit",
                    "is_real_md": True,
                    "engine": "GROMACS",
                    "wild_type": {
                        "simulation_parameters": {
                            "batch_id": "mdrep_poll_summary",
                            "replicate_variant": "WT",
                            "replicate_index": 1,
                            "run_seed": 1234,
                        },
                        "structural_stability": {
                            "rmsd_drift_nm": 0.12,
                            "mean_rmsf_nm": 0.24,
                            "is_stable": True,
                        },
                        "compactness": {
                            "rg_change_nm": 0.03,
                            "sasa_initial_nm2": 10.0,
                            "sasa_final_nm2": 10.8,
                        },
                    },
                    "artifacts": [{"name": "rmsd.xvg", "object_name": "md/job-audit/rmsd.xvg"}],
                    "artifact_manifest": {"version": 1, "total_count": 1, "groups": {"analysis": []}},
                    "interpretation": {"verdict": "stable_short_run", "confidence": "low", "evidence_level": "smoke"},
                    "batch_replicate_summary": {
                        "lipase_evidence_context": {
                            "status": "ready",
                            "counts": {"exact_mutation_matches": 1, "position_matches": 2, "search_matches": 3},
                            "strongest_evidence_level": "article_level",
                        }
                    },
                },
            },
            "error": None,
            "progress": 100,
            "stage": "finalize",
        },
    )

    poll_response = await client.get("/api/tools/tasks/audit-poll-task-id")
    audit_response = await client.get("/api/tools/tasks/audit-poll-task-id/audit")

    assert poll_response.status_code == 200
    assert audit_response.status_code == 200
    audit = audit_response.json()
    assert audit["status"] == "completed"
    assert audit["progress"] == 100
    assert audit["stage"] == "finalize"
    assert audit["result_summary"]["job_id"] == "job-audit"
    assert audit["result_summary"]["artifact_count"] == 1
    assert audit["result_summary"]["interpretation"]["verdict"] == "stable_short_run"
    assert audit["result_summary"]["lipase_evidence"] == {
        "status": "ready",
        "source": "kwb_lipase_db",
        "exact_mutation_matches": 1,
        "position_matches": 2,
        "search_matches": 3,
        "strongest_evidence_level": "article_level",
    }
    assert audit["result_summary"]["md_replicate"] == {
        "batch_id": "mdrep_poll_summary",
        "replicate_variant": "WT",
        "replicate_index": 1,
        "run_seed": 1234,
        "rmsd_drift_nm": 0.12,
        "mean_rmsf_nm": 0.24,
        "rg_change_nm": 0.03,
        "sasa_change_nm2": 0.8,
        "is_stable": True,
    }
    assert audit["artifact_manifest"]["total_count"] == 1
    assert audit["duration_seconds"] is not None
    assert audit["failure_class"] is None
    assert audit["is_slow"] is False


async def test_tool_task_audit_classifies_failure_and_duration(client, session):
    user = await _create_user(session, "tool-task-audit-classify@example.com")
    submitted = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=45)
    terminal = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(
        ToolTaskAudit(
            task_id="classified-failure-task-id",
            user_id=user.id,
            tool_name="gromacs_md",
            status="failed",
            queue="md_cpu",
            error="GROMACS timed out after time limit",
            submitted_at=submitted,
            terminal_recorded_at=terminal,
        )
    )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/tools/tasks/classified-failure-task-id/audit")

    assert response.status_code == 200
    audit = response.json()
    assert audit["duration_seconds"] >= 45 * 60 - 5
    assert audit["failure_class"] == "timeout"
    assert audit["is_slow"] is True


async def test_tool_task_audit_rejects_other_user(client, session, monkeypatch):
    owner = await _create_user(session, "tool-task-audit-owner@example.com")
    intruder = await _create_user(session, "tool-task-audit-intruder@example.com")
    await session.commit()
    monkeypatch.setattr("app.api.tools.dispatch_tool", lambda tool_name, params: "audit-owner-task-id")
    client.cookies.set("pa_token", create_access_token(owner.id))
    await client.post(
        "/api/tools/gromacs_md/submit",
        json={"params": {"pdb_object_name": "uploads/owner/input.pdb"}},
    )
    client.cookies.set("pa_token", create_access_token(intruder.id))

    response = await client.get("/api/tools/tasks/audits")

    assert response.status_code == 200
    assert response.json()["count"] == 0


async def test_admin_task_audit_requires_admin_role(client, session):
    user = await _create_user(session, "tool-task-admin-audit-researcher@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/tools/admin/tasks/audits")

    assert response.status_code == 403
    assert response.json()["detail"] == "Administrator privileges required"


async def test_admin_task_audit_lists_cross_user_records(client, session, monkeypatch):
    owner = await _create_user(session, "tool-task-admin-audit-owner@example.com")
    admin = await _create_user(session, "tool-task-admin-audit-admin@example.com")
    admin.role = "admin"
    await session.commit()
    monkeypatch.setattr("app.api.tools.dispatch_tool", lambda tool_name, params: "admin-visible-task-id")
    client.cookies.set("pa_token", create_access_token(owner.id))
    submit_response = await client.post(
        "/api/tools/gromacs_md/submit",
        json={"params": {"pdb_object_name": "uploads/owner/input.pdb"}},
    )
    client.cookies.set("pa_token", create_access_token(admin.id))

    list_response = await client.get("/api/tools/admin/tasks/audits")
    detail_response = await client.get("/api/tools/admin/tasks/admin-visible-task-id/audit")

    assert submit_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()["count"] >= 1
    assert any(item["task_id"] == "admin-visible-task-id" for item in list_response.json()["audits"])
    assert list_response.json()["summary"]["total"] >= 1
    assert "runtime_environment" in list_response.json()["summary"]
    assert detail_response.status_code == 200
    assert detail_response.json()["user_id"] == owner.id


async def test_admin_task_audit_summary_requires_admin_role(client, session):
    user = await _create_user(session, "tool-task-admin-summary-researcher@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/tools/admin/tasks/audits/summary")

    assert response.status_code == 403


async def test_admin_task_audit_summary_reports_failure_trends(client, session):
    admin = await _create_user(session, "tool-task-admin-summary-admin@example.com")
    admin.role = "admin"
    submitted = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=31)
    terminal = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add(
        ToolTaskAudit(
            task_id="summary-timeout-task-id",
            user_id=admin.id,
            tool_name="gromacs_md",
            status="failed",
            queue="md_cpu",
            error="GROMACS timeout while running mdrun",
            submitted_at=submitted,
            terminal_recorded_at=terminal,
        )
    )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    response = await client.get("/api/tools/admin/tasks/audits/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["failure_counts"]["timeout"] >= 1
    assert body["slow_count"] >= 1
    assert body["duration"]["max_seconds"] >= 31 * 60 - 5
    assert body["recent_failures"][0]["failure_class"] == "timeout"
    assert body["failure_trend"][0]["total_failures"] >= 1
    assert body["failure_trend"][0]["failure_counts"]["timeout"] >= 1
    assert body["alerting"]["mode"] == "summary_only"
    assert body["alerting"]["external_delivery"] == "not_configured"
    assert body["runtime_environment"]["python_version"]


async def test_admin_task_audit_filters_records(client, session):
    admin = await _create_user(session, "tool-task-admin-filter-admin@example.com")
    admin.role = "admin"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add_all(
        [
            ToolTaskAudit(
                task_id="filter-md-timeout-task-id",
                user_id=admin.id,
                tool_name="gromacs_md",
                status="failed",
                queue="md_cpu",
                error="GROMACS timeout during mdrun",
                submitted_at=now - timedelta(hours=2),
                terminal_recorded_at=now,
            ),
            ToolTaskAudit(
                task_id="filter-blast-success-task-id",
                user_id=admin.id,
                tool_name="blast_search",
                status="completed",
                queue="default",
                submitted_at=now - timedelta(days=3),
                terminal_recorded_at=now - timedelta(days=3, minutes=-1),
            ),
            ToolTaskAudit(
                task_id="filter-md-missing-task-id",
                user_id=admin.id,
                tool_name="gromacs_md",
                status="failed",
                queue="md_cpu",
                error="input file not found",
                submitted_at=now - timedelta(minutes=10),
                terminal_recorded_at=now,
            ),
        ]
    )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    response = await client.get(
        "/api/tools/admin/tasks/audits",
        params={
            "tool": "gromacs_md",
            "status": "failed",
            "queue": "md_cpu",
            "failure_class": "timeout",
            "slow_only": "true",
            "submitted_after": (now - timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["audits"][0]["task_id"] == "filter-md-timeout-task-id"
    assert body["summary"]["failure_counts"]["timeout"] == 1
    assert body["summary"]["slow_count"] == 1
    assert body["summary"]["failure_trend"][0]["total_failures"] == 1
    assert body["summary"]["alerting"]["status"] == "ok"


async def test_admin_task_audit_export_honors_filters(client, session):
    admin = await _create_user(session, "tool-task-admin-export-filter-admin@example.com")
    admin.role = "admin"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session.add_all(
        [
            ToolTaskAudit(
                task_id="csv-filter-timeout-task-id",
                user_id=admin.id,
                tool_name="gromacs_md",
                status="failed",
                queue="md_cpu",
                error="timeout while running gmx",
                submitted_at=now - timedelta(hours=1),
                terminal_recorded_at=now,
            ),
            ToolTaskAudit(
                task_id="csv-filter-success-task-id",
                user_id=admin.id,
                tool_name="gromacs_md",
                status="completed",
                queue="md_cpu",
                submitted_at=now,
                terminal_recorded_at=now,
            ),
        ]
    )
    await session.commit()
    client.cookies.set("pa_token", create_access_token(admin.id))

    response = await client.get("/api/tools/admin/tasks/audits/export", params={"failed_only": "true"})

    assert response.status_code == 200
    assert "csv-filter-timeout-task-id" in response.text
    assert "csv-filter-success-task-id" not in response.text


async def test_admin_task_audit_exports_sanitized_csv(client, session, monkeypatch):
    owner = await _create_user(session, "tool-task-admin-export-owner@example.com")
    admin = await _create_user(session, "tool-task-admin-export-admin@example.com")
    admin.role = "admin"
    await session.commit()
    monkeypatch.setattr("app.api.tools.dispatch_tool", lambda tool_name, params: "admin-export-task-id")
    client.cookies.set("pa_token", create_access_token(owner.id))
    submit_response = await client.post(
        "/api/tools/gromacs_md/submit",
        json={
            "params": {
                "pdb_object_name": "uploads/owner/input.pdb",
                "pdb_data": "ATOM secret payload that must not appear in export",
            }
        },
    )
    client.cookies.set("pa_token", create_access_token(admin.id))

    export_response = await client.get("/api/tools/admin/tasks/audits/export")

    assert submit_response.status_code == 200
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("text/csv")
    assert "tool-task-audits.csv" in export_response.headers["content-disposition"]
    assert "admin-export-task-id" in export_response.text
    assert "uploads/owner/input.pdb" in export_response.text
    assert "duration_seconds" in export_response.text
    assert "failure_class" in export_response.text
    assert "is_slow" in export_response.text
    assert "python_version" in export_response.text
    assert "platform" in export_response.text
    assert "secret payload" not in export_response.text
    assert "redacted" in export_response.text
    assert "true" in export_response.text


async def test_md_protocol_api_lists_templates(client, session):
    user = await _create_user(session, "md-protocol-list@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.get("/api/tools/md/protocols")

    assert response.status_code == 200
    body = response.json()
    assert body["default_protocol_id"] == "smoke_short"
    assert any(protocol["id"] == "production_review" for protocol in body["protocols"])


async def test_md_protocol_api_resolves_allowed_overrides(client, session):
    user = await _create_user(session, "md-protocol-resolve@example.com")
    await session.commit()
    client.cookies.set("pa_token", create_access_token(user.id))

    response = await client.post(
        "/api/tools/md/protocols/smoke_short/resolve",
        json={"overrides": {"simulation_time_ns": 0.2, "unsafe_shell": "ignored"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["protocol_id"] == "smoke_short"
    assert body["parameters"]["simulation_time_ns"] == 0.2
    assert "unsafe_shell" not in body["parameters"]


async def test_tool_task_polling_includes_cancel_metadata(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-poll-cancel@example.com")
    await session.commit()
    await record_tool_task_owner("poll-cancel-task-id", user.id, "gromacs_md")
    await record_tool_task_runtime_policy("poll-cancel-task-id", queue="md_cpu", soft_time_limit=3600, time_limit=5400)
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr("app.api.tools.cancel_task", lambda task_id: True)
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "pending",
            "result": None,
            "error": None,
            "progress": 0,
        },
    )

    cancel_response = await client.post("/api/tools/tasks/poll-cancel-task-id/cancel")
    poll_response = await client.get("/api/tools/tasks/poll-cancel-task-id")

    assert cancel_response.status_code == 200
    assert poll_response.status_code == 200
    body = poll_response.json()
    assert body["tool"] == "gromacs_md"
    assert body["queue"] == "md_cpu"
    assert body["soft_time_limit"] == 3600
    assert body["time_limit"] == 5400
    assert body["cancel_requested"] is True
    assert body["cancel_requested_at"] == cancel_response.json()["cancel_requested_at"]
    assert body["audit"]["task_id"] == "poll-cancel-task-id"
    assert body["audit"]["tool"] == "gromacs_md"
    assert body["audit"]["queue"] == "md_cpu"
    assert body["audit"]["runtime_policy"]["time_limit"] == 5400
    assert body["audit"]["cancellation"]["requested"] is True


async def test_tool_task_polling_records_canceled_terminal_state(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-terminal@example.com")
    await session.commit()
    await record_tool_task_owner("terminal-cancel-task-id", user.id, "gromacs_md")
    await record_tool_task_runtime_policy("terminal-cancel-task-id", queue="md_cpu", soft_time_limit=3600, time_limit=5400)
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "canceled",
            "result": None,
            "error": "terminated by revoke",
            "progress": 100,
        },
    )

    response = await client.get("/api/tools/tasks/terminal-cancel-task-id")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "canceled"
    assert body["terminal_status"] == "canceled"
    assert body["queue"] == "md_cpu"


async def test_tool_task_polling_coerces_terminated_cancel_request_to_canceled(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-terminated-cancel@example.com")
    await session.commit()
    await record_tool_task_owner("terminated-cancel-task-id", user.id, "gromacs_md")
    await record_tool_task_runtime_policy("terminated-cancel-task-id", queue="md_cpu", soft_time_limit=3600, time_limit=5400)
    await record_tool_task_cancel_requested("terminated-cancel-task-id", user.id)
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "failed",
            "result": None,
            "error": "Task backend returned unexpected payload: terminated",
            "progress": 100,
        },
    )

    response = await client.get("/api/tools/tasks/terminated-cancel-task-id")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "canceled"
    assert body["terminal_status"] == "canceled"
    assert body["error"] is None


async def test_tool_task_polling_records_md_artifact_owner_for_download(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-artifact-owner@example.com")
    await session.commit()
    await record_tool_task_owner("artifact-task-id", user.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "completed",
            "result": {
                "status": "completed",
                "tool": "gromacs_md",
                "result": {
                    "job_id": "job-1",
                    "artifacts": [
                        {
                            "name": "rmsd.xvg",
                            "object_name": "md/job-1/rmsd.xvg",
                            "download_url": "/api/files/md/job-1/rmsd.xvg/download?filename=rmsd.xvg",
                        }
                    ],
                },
            },
            "error": None,
            "progress": 100,
        },
    )
    async def fake_download_file(object_name: str):
        return b"@ title rmsd\n0 0.1\n"

    monkeypatch.setattr("app.services.storage.download_file", fake_download_file)

    poll_response = await client.get("/api/tools/tasks/artifact-task-id")
    download_response = await client.get("/api/files/md/job-1/rmsd.xvg/download?filename=rmsd.xvg")

    assert poll_response.status_code == 200
    assert download_response.status_code == 200
    assert download_response.text == "@ title rmsd\n0 0.1\n"
    assert download_response.headers["content-type"].startswith("text/plain")
    assert "filename=rmsd.xvg" in download_response.headers["content-disposition"]

    owner = await get_tool_artifact_owner("md/job-1/rmsd.xvg")
    assert owner is not None
    assert owner["user_id"] == user.id
    assert owner["tool"] == "gromacs_md"
    assert owner["task_id"] == "artifact-task-id"


async def test_tool_task_polling_backfills_artifact_filename_query(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-artifact-filename@example.com")
    await session.commit()
    await record_tool_task_owner("artifact-filename-task-id", user.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "completed",
            "result": {
                "status": "completed",
                "tool": "gromacs_md",
                "result": {
                    "job_id": "job-compat",
                    "artifacts": [
                        {
                            "name": "rmsf.xvg",
                            "object_name": "md/job-compat/rmsf.xvg",
                            "download_url": "/api/files/md/job-compat/rmsf.xvg/download",
                        }
                    ],
                },
            },
            "error": None,
            "progress": 100,
        },
    )

    response = await client.get("/api/tools/tasks/artifact-filename-task-id")

    assert response.status_code == 200
    body = response.json()
    artifacts = body["result"]["result"]["artifacts"]
    assert artifacts[0]["download_url"].endswith("/api/files/md/job-compat/rmsf.xvg/download?filename=rmsf.xvg")


async def test_tool_task_artifact_bundle_download_returns_zip(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-artifact-bundle@example.com")
    await session.commit()
    await record_tool_task_owner("artifact-bundle-task-id", user.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "completed",
            "result": {
                "status": "completed",
                "tool": "gromacs_md",
                "result": {
                    "job_id": "job-bundle",
                    "artifacts": [
                        {
                            "name": "rmsd.xvg",
                            "object_name": "md/job-bundle/rmsd.xvg",
                            "download_url": "/api/files/md/job-bundle/rmsd.xvg/download?filename=rmsd.xvg",
                            "category": "analysis",
                        },
                        {
                            "name": "topol.top",
                            "object_name": "md/job-bundle/topol.top",
                            "download_url": "/api/files/md/job-bundle/topol.top/download?filename=topol.top",
                            "category": "topology",
                        },
                    ],
                    "artifact_manifest": {
                        "version": 1,
                        "total_count": 2,
                        "groups": {
                            "analysis": [{"name": "rmsd.xvg", "object_name": "md/job-bundle/rmsd.xvg"}],
                            "topology": [{"name": "topol.top", "object_name": "md/job-bundle/topol.top"}],
                        },
                    },
                },
            },
            "error": None,
            "progress": 100,
        },
    )

    async def fake_download_file(object_name: str):
        payloads = {
            "md/job-bundle/rmsd.xvg": b"@ title rmsd\n0 0.1\n",
            "md/job-bundle/topol.top": b"; topology\n",
        }
        return payloads[object_name]

    monkeypatch.setattr("app.services.storage.download_file", fake_download_file)
    monkeypatch.setattr("app.api.tools.storage.download_file", fake_download_file)

    response = await client.get("/api/tools/tasks/artifact-bundle-task-id/artifacts/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "gromacs_md-artifacts" not in response.headers["content-disposition"] or "artifacts.zip" in response.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert "analysis/rmsd.xvg" in names
    assert "topology/topol.top" in names
    assert "manifest/artifact_manifest.json" in names
    assert archive.read("analysis/rmsd.xvg") == b"@ title rmsd\n0 0.1\n"


async def test_tool_task_artifact_bundle_download_rejects_other_user(client, session):
    owner = await _create_user(session, "tool-task-bundle-owner@example.com")
    intruder = await _create_user(session, "tool-task-bundle-intruder@example.com")
    await session.commit()
    await record_tool_task_owner("owned-bundle-task-id", owner.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(intruder.id))

    response = await client.get("/api/tools/tasks/owned-bundle-task-id/artifacts/download")

    assert response.status_code == 403
    assert response.json()["detail"] == "Task does not belong to current user"


async def test_tool_task_artifact_bundle_download_rejects_incomplete_task(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-bundle-pending@example.com")
    await session.commit()
    await record_tool_task_owner("pending-bundle-task-id", user.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "running",
            "result": {
                "status": "running",
                "tool": "gromacs_md",
                "result": {
                    "artifacts": [
                        {
                            "name": "rmsd.xvg",
                            "object_name": "md/job-pending/rmsd.xvg",
                        }
                    ],
                },
            },
            "error": None,
            "progress": 55,
        },
    )

    response = await client.get("/api/tools/tasks/pending-bundle-task-id/artifacts/download")

    assert response.status_code == 409
    assert response.json()["detail"] == "Artifacts are available only after the task completes successfully"


async def test_tool_task_artifact_bundle_download_rejects_missing_artifacts(client, session, monkeypatch):
    user = await _create_user(session, "tool-task-bundle-empty@example.com")
    await session.commit()
    await record_tool_task_owner("empty-bundle-task-id", user.id, "gromacs_md")
    client.cookies.set("pa_token", create_access_token(user.id))
    monkeypatch.setattr(
        "app.api.tools.get_task_status",
        lambda task_id: {
            "task_id": task_id,
            "status": "completed",
            "result": {
                "status": "completed",
                "tool": "gromacs_md",
                "result": {
                    "artifacts": [],
                },
            },
            "error": None,
            "progress": 100,
        },
    )

    response = await client.get("/api/tools/tasks/empty-bundle-task-id/artifacts/download")

    assert response.status_code == 404
    assert response.json()["detail"] == "No downloadable artifacts found for this task"


async def test_file_download_rejects_md_artifact_without_owner_binding():
    try:
        await _assert_file_download_access("md/job-2/rmsf.xvg", 123)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
        assert getattr(exc, "detail", None) == "Access denied for this file"
    else:
        raise AssertionError("Expected 403 for unbound MD artifact download")


async def test_file_download_rejects_md_artifact_bound_to_other_user():
    await record_tool_task_owner("artifact-other-user-task-id", 42, "gromacs_md")
    await record_tool_artifact_owner(
        "md/job-3/rmsd.xvg",
        42,
        tool_name="gromacs_md",
        task_id="artifact-other-user-task-id",
    )

    try:
        await _assert_file_download_access("md/job-3/rmsd.xvg", 7)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
        assert getattr(exc, "detail", None) == "Access denied for this file"
    else:
        raise AssertionError("Expected 403 for artifact download by non-owner")


async def test_blast_search_marks_successful_run_as_live(monkeypatch):
    import app.tools.blast_search as blast_module

    async def fake_get_cached_result(*args, **kwargs):
        return None

    async def fake_set_cached_result(*args, **kwargs):
        return None

    async def fake_run_blast(*args, **kwargs):
        return [{"accession": "P12345", "best_identity_percent": 88.0}]

    monkeypatch.setattr(blast_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(blast_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(blast_module, "_run_blast", fake_run_blast)

    payload = await blast_module.blast_search("ACDEFGHIKL", database="swissprot", max_results=1)

    assert payload["status"] == "completed"
    assert payload["evidence_source"]["status"] == "live"
    assert payload["evidence_source"]["mode"] == "ncbi_blast_rest"
    assert payload["evidence_source"]["live_query_executed"] is True


async def test_blast_search_sends_ncbi_key_without_leaking_details(monkeypatch):
    import app.tools.blast_search as blast_module

    calls = []

    async def fake_get_cached_result(*args, **kwargs):
        return None

    async def fake_set_cached_result(*args, **kwargs):
        return None

    async def fake_sleep(*args, **kwargs):
        return None

    class FakeResponse:
        def __init__(self, text, status_code=200, headers=None):
            self.text = text
            self.status_code = status_code
            self.headers = headers or {}

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, data):
            calls.append(("post", dict(data)))
            return FakeResponse("RID = TEST-RID\nRTOE = 1\n")

        async def get(self, url, params):
            calls.append(("get", dict(params)))
            return FakeResponse("Status=READY\n")

    monkeypatch.setattr(blast_module.settings, "NCBI_API_KEY", "secret-ncbi-key")
    monkeypatch.setattr(blast_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(blast_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(blast_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(blast_module.httpx, "AsyncClient", FakeAsyncClient)

    payload = await blast_module.blast_search("ACDEFGHIKL", database="swissprot", max_results=1)

    assert calls[0][1]["NCBI_API_KEY"] == "secret-ncbi-key"
    assert calls[1][1]["NCBI_API_KEY"] == "secret-ncbi-key"
    details = payload["evidence_source"]["details"]
    assert details["api_key_configured"] is True
    assert "rate_limit_policy" in details
    assert "secret-ncbi-key" not in str(details)


async def test_blast_search_parses_direct_xml_hits_without_ready_marker(monkeypatch):
    import app.tools.blast_search as blast_module

    async def fake_get_cached_result(*args, **kwargs):
        return None

    async def fake_set_cached_result(*args, **kwargs):
        return None

    async def fake_sleep(*args, **kwargs):
        return None

    class FakeResponse:
        def __init__(self, text, status_code=200, headers=None):
            self.text = text
            self.status_code = status_code
            self.headers = headers or {}

        def raise_for_status(self):
            return None

    direct_xml = """
    <BlastOutput>
      <BlastOutput_iterations>
        <Iteration>
          <Hit>
            <Hit_num>1</Hit_num>
            <Hit_id>pdb|1WKY|A</Hit_id>
            <Hit_def>Chain A, endo-beta-1,4-Mannanase [Bacillus sp. JAMB-602]</Hit_def>
            <Hit_accession>1WKY_A</Hit_accession>
            <Hit_len>464</Hit_len>
            <Hsp>
              <Hsp_num>1</Hsp_num>
              <Hsp_bit-score>436.032</Hsp_bit-score>
              <Hsp_score>1120</Hsp_score>
              <Hsp_evalue>2.7e-152</Hsp_evalue>
              <Hsp_query-from>2</Hsp_query-from>
              <Hsp_query-to>297</Hsp_query-to>
              <Hsp_hit-from>8</Hsp_hit-from>
              <Hsp_hit-to>303</Hsp_hit-to>
              <Hsp_identity>204</Hsp_identity>
              <Hsp_positive>245</Hsp_positive>
              <Hsp_gaps>0</Hsp_gaps>
              <Hsp_align-len>296</Hsp_align-len>
            </Hsp>
          </Hit>
        </Iteration>
      </BlastOutput_iterations>
    </BlastOutput>
    """

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, data):
            return FakeResponse("RID = TEST-RID\nRTOE = 1\n")

        async def get(self, url, params):
            return FakeResponse(direct_xml)

    monkeypatch.setattr(blast_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(blast_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(blast_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(blast_module.httpx, "AsyncClient", FakeAsyncClient)

    payload = await blast_module.blast_search("ACDEFGHIKL", database="pdb", max_results=1)

    assert payload["status"] == "completed"
    assert payload["results_count"] == 1
    assert payload["results"][0]["accession"] == "1WKY_A"
    assert payload["results"][0]["best_identity_percent"] == 68.9


async def test_blast_search_marks_cache_hit_as_degraded(monkeypatch):
    import app.tools.blast_search as blast_module

    async def fake_get_cached_result(*args, **kwargs):
        return {
            "status": "completed",
            "results": [{"accession": "P12345"}],
            "cache": {"hit": True, "stale": False},
            "evidence_source": {
                "source": "NCBI BLAST",
                "status": "live",
                "mode": "ncbi_blast_rest",
                "live_query_executed": True,
            },
        }

    async def fail_run_blast(*args, **kwargs):
        raise AssertionError("cache hit should not run BLAST")

    monkeypatch.setattr(blast_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(blast_module, "_run_blast", fail_run_blast)

    payload = await blast_module.blast_search("ACDEFGHIKL", database="swissprot", max_results=1)

    assert payload["status"] == "completed"
    assert payload["evidence_source"]["status"] == "degraded"
    assert payload["evidence_source"]["mode"] == "cache_hit"
    assert payload["evidence_source"]["live_query_executed"] is False


async def test_blast_search_marks_runtime_failure_as_degraded(monkeypatch):
    import app.tools.blast_search as blast_module

    async def fake_get_cached_result(*args, **kwargs):
        return None

    async def fake_set_cached_result(*args, **kwargs):
        return None

    async def fail_run_blast(*args, **kwargs):
        raise TimeoutError("BLAST_TIMEOUT: test timeout")

    monkeypatch.setattr(blast_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(blast_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(blast_module, "_run_blast", fail_run_blast)

    payload = await blast_module.blast_search("ACDEFGHIKL", database="swissprot", max_results=1)

    assert payload["status"] == "degraded"
    assert payload["error_code"] == "BLAST_TIMEOUT"
    assert payload["evidence_source"]["status"] == "degraded"
    assert payload["evidence_source"]["mode"] == "live_query_failed"
    assert payload["evidence_source"]["live_query_executed"] is False
    assert payload["evidence_source"]["details"]["attempted_live_query"] is True


async def test_sequence_search_marks_uniprot_keyword_success_as_live(monkeypatch):
    import app.tools.sequence_search as search_module

    async def fake_get_cached_result(*args, **kwargs):
        return None

    async def fake_set_cached_result(*args, **kwargs):
        return None

    class FakeUniProtClient:
        async def search(self, query, max_results=10):
            return [{"accession": "Q69IF8", "protein_name": "demo"}]

        async def close(self):
            return None

    monkeypatch.setattr(search_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(search_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(search_module, "UniProtClient", FakeUniProtClient)

    payload = await search_module.sequence_search("Q69IF8", max_results=1)

    assert payload["status"] == "completed"
    assert payload["evidence_source"]["status"] == "live"
    assert payload["evidence_source"]["mode"] == "uniprotkb_search_rest"
    assert payload["evidence_source"]["live_query_executed"] is True


async def test_sequence_search_blast_sends_ncbi_key_without_leaking_details(monkeypatch):
    import app.tools.sequence_search as search_module

    calls = []

    async def fake_get_cached_result(*args, **kwargs):
        return None

    async def fake_set_cached_result(*args, **kwargs):
        return None

    async def fake_sleep(*args, **kwargs):
        return None

    class FakeResponse:
        def __init__(self, text, status_code=200, headers=None):
            self.text = text
            self.status_code = status_code
            self.headers = headers or {}

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def post(self, url, data):
            calls.append(("post", dict(data)))
            return FakeResponse("RID = TEST-RID\nRTOE = 1\n")

        async def get(self, url, params):
            calls.append(("get", dict(params)))
            return FakeResponse("Status=READY\n")

        async def aclose(self):
            return None

    monkeypatch.setattr(search_module.settings, "NCBI_API_KEY", "secret-ncbi-key")
    monkeypatch.setattr(search_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(search_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(search_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(search_module.httpx, "AsyncClient", FakeAsyncClient)

    payload = await search_module.sequence_search(_SD_388_SEQUENCE[:40], database="nr", max_results=1)

    assert calls[0][1]["NCBI_API_KEY"] == "secret-ncbi-key"
    assert calls[1][1]["NCBI_API_KEY"] == "secret-ncbi-key"
    details = payload["evidence_source"]["details"]
    assert details["api_key_configured"] is True
    assert "rate_limit_policy" in details
    assert "secret-ncbi-key" not in str(details)


async def test_sequence_search_marks_cache_hit_as_degraded(monkeypatch):
    import app.tools.sequence_search as search_module

    async def fake_get_cached_result(*args, **kwargs):
        return {
            "query": "Q69IF8",
            "query_type": "keyword",
            "database": "uniprot",
            "results_count": 1,
            "results": [{"accession": "Q69IF8"}],
            "status": "completed",
            "cache": {"hit": True, "stale": False},
            "evidence_source": {
                "source": "UniProt REST",
                "status": "live",
                "mode": "uniprotkb_search_rest",
                "endpoint": "https://rest.uniprot.org/uniprotkb/search",
                "live_query_executed": True,
            },
        }

    class FailUniProtClient:
        async def search(self, *args, **kwargs):
            raise AssertionError("cache hit should not query UniProt")

        async def close(self):
            return None

    monkeypatch.setattr(search_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(search_module, "UniProtClient", FailUniProtClient)

    payload = await search_module.sequence_search("Q69IF8", max_results=1)

    assert payload["status"] == "completed"
    assert payload["evidence_source"]["status"] == "degraded"
    assert payload["evidence_source"]["mode"] == "cache_hit"
    assert payload["evidence_source"]["live_query_executed"] is False


async def test_literature_live_search_marks_successful_run_as_live(monkeypatch):
    import app.tools.literature_live_search as literature_module
    from app.core.config import settings as app_settings

    calls = []
    cache_writes = []

    async def fake_get_cached_result(*args, **kwargs):
        return None

    async def fake_set_cached_result(*args, **kwargs):
        cache_writes.append((args, kwargs))

    class FakePubMedClient:
        async def search(self, *, query="", doi="", pmid="", max_results=10):
            calls.append(("pubmed", query, doi, pmid, max_results))
            return [
                {
                    "source": "pubmed",
                    "pmid": "12345",
                    "doi": "10.1000/demo",
                    "title": "Lipase thermostability demo",
                    "journal": "Demo Journal",
                    "published": "2025",
                    "authors": ["A Author"],
                    "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
                }
            ]

        async def close(self):
            return None

    class FakeCrossrefClient:
        async def search(self, *, query="", doi="", pmid="", max_results=10):
            calls.append(("crossref", query, doi, pmid, max_results))
            return [
                {
                    "source": "crossref",
                    "pmid": "",
                    "doi": "10.1000/other",
                    "title": "Crossref enzyme paper",
                    "journal": "Crossref Journal",
                    "published": "2024",
                    "authors": ["B Author"],
                    "url": "https://doi.org/10.1000/other",
                }
            ]

        async def close(self):
            return None

    monkeypatch.setattr(literature_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(literature_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(app_settings, "NCBI_API_KEY", "secret-ncbi-key")
    monkeypatch.setattr(literature_module, "PubMedEUtilitiesClient", FakePubMedClient)
    monkeypatch.setattr(literature_module, "CrossrefClient", FakeCrossrefClient)

    payload = await ToolRegistry.execute(
        "literature_live_search",
        {"query": "lipase thermostability", "doi": "10.1000/demo", "max_results": 2},
    )

    assert payload["status"] == "completed"
    assert payload["results_count"] == 2
    assert payload["sources_queried"] == ["pubmed", "crossref"]
    assert payload["evidence_source"]["status"] == "live"
    assert payload["evidence_source"]["mode"] == "pubmed_crossref_rest"
    assert payload["evidence_source"]["live_query_executed"] is True
    assert payload["evidence_source"]["details"]["api_key_configured"] is True
    assert "secret-ncbi-key" not in str(payload["evidence_source"]["details"])
    assert calls == [
        ("pubmed", "lipase thermostability", "10.1000/demo", "", 2),
        ("crossref", "lipase thermostability", "10.1000/demo", "", 2),
    ]
    assert cache_writes[0][0][0] == "literature_live_search"
    assert cache_writes[0][0][1] == {
        "query": "lipase thermostability",
        "doi": "10.1000/demo",
        "pmid": "",
        "max_results": 2,
    }


async def test_pubmed_eutilities_client_sends_ncbi_api_key(monkeypatch):
    import app.tools.literature_live_search as literature_module
    from app.core.config import settings as app_settings

    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.status_code = 200
            self.headers = {}
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def get(self, url, params):
            calls.append((url, dict(params)))
            if url == literature_module.PUBMED_ESEARCH_URL:
                return FakeResponse({"esearchresult": {"idlist": ["12345"]}})
            return FakeResponse({
                "result": {
                    "uids": ["12345"],
                    "12345": {
                        "title": "Demo PubMed record",
                        "articleids": [],
                        "authors": [],
                    },
                }
            })

        async def aclose(self):
            return None

    monkeypatch.setattr(app_settings, "NCBI_API_KEY", "secret-ncbi-key")
    monkeypatch.setattr(literature_module.httpx, "AsyncClient", FakeAsyncClient)

    client = literature_module.PubMedEUtilitiesClient()
    try:
        results = await client.search(query="lipase", max_results=1)
    finally:
        await client.close()

    assert results[0]["pmid"] == "12345"
    assert calls[0][1]["api_key"] == "secret-ncbi-key"
    assert calls[1][1]["api_key"] == "secret-ncbi-key"


async def test_literature_live_search_marks_cache_hit_as_degraded(monkeypatch):
    import app.tools.literature_live_search as literature_module

    calls = []

    async def fake_get_cached_result(namespace, params, **kwargs):
        calls.append((namespace, params, kwargs))
        return {
            "status": "completed",
            "query": "lipase thermostability",
            "doi": "",
            "pmid": "",
            "max_results": 1,
            "results_count": 1,
            "results": [{"source": "pubmed", "pmid": "12345", "title": "Cached literature"}],
            "cache": {"hit": True, "stale": False},
            "evidence_source": {
                "source": "PubMed E-utilities; Crossref REST",
                "status": "live",
                "mode": "pubmed_crossref_rest",
                "live_query_executed": True,
            },
        }

    async def fake_set_cached_result(*args, **kwargs):
        raise AssertionError("cache hit should not rewrite the literature cache")

    class FailPubMedClient:
        async def search(self, *args, **kwargs):
            raise AssertionError("cache hit should not query PubMed")

        async def close(self):
            return None

    class FailCrossrefClient:
        async def search(self, *args, **kwargs):
            raise AssertionError("cache hit should not query Crossref")

        async def close(self):
            return None

    monkeypatch.setattr(literature_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(literature_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(literature_module, "PubMedEUtilitiesClient", FailPubMedClient)
    monkeypatch.setattr(literature_module, "CrossrefClient", FailCrossrefClient)

    payload = await ToolRegistry.execute(
        "literature_live_search",
        {"query": "lipase thermostability", "max_results": 1},
    )

    assert payload["status"] == "completed"
    assert payload["results_count"] == 1
    assert payload["evidence_source"]["status"] == "degraded"
    assert payload["evidence_source"]["mode"] == "cache_hit"
    assert payload["evidence_source"]["live_query_executed"] is False
    assert calls == [
        (
            "literature_live_search",
            {"query": "lipase thermostability", "doi": "", "pmid": "", "max_results": 1},
            {},
        )
    ]


async def test_literature_live_search_returns_stale_cache_after_live_failure(monkeypatch):
    import app.tools.literature_live_search as literature_module

    cache_reads = []

    async def fake_get_cached_result(namespace, params, **kwargs):
        cache_reads.append((namespace, params, kwargs))
        if kwargs.get("allow_stale"):
            return {
                "status": "completed",
                "query": "",
                "doi": "",
                "pmid": "12345",
                "max_results": 1,
                "results_count": 1,
                "results": [{"source": "pubmed", "pmid": "12345", "title": "Stale literature"}],
                "cache": {"hit": True, "stale": True},
                "evidence_source": {
                    "source": "PubMed E-utilities; Crossref REST",
                    "status": "live",
                    "mode": "pubmed_crossref_rest",
                    "live_query_executed": True,
                },
            }
        return None

    class FailingPubMedClient:
        async def search(self, *args, **kwargs):
            raise TimeoutError("pubmed timeout")

        async def close(self):
            return None

    class FailingCrossrefClient:
        async def search(self, *args, **kwargs):
            request = httpx.Request("GET", "https://api.crossref.org/works")
            response = httpx.Response(429, request=request, headers={"Retry-After": "5"})
            raise httpx.HTTPStatusError("crossref rate limited", request=request, response=response)

        async def close(self):
            return None

    monkeypatch.setattr(literature_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(literature_module, "PubMedEUtilitiesClient", FailingPubMedClient)
    monkeypatch.setattr(literature_module, "CrossrefClient", FailingCrossrefClient)

    payload = await ToolRegistry.execute(
        "literature_live_search",
        {"pmid": "12345", "max_results": 1},
    )

    assert payload["status"] == "degraded"
    assert payload["warning"] == "Live literature lookup failed; returned stale cached literature result."
    assert payload["results_count"] == 1
    assert payload["sources_queried"] == []
    assert payload["cache"]["stale"] is True
    assert payload["errors"]["pubmed"] == "pubmed timeout"
    assert "crossref" in payload["errors"]
    assert payload["evidence_source"]["status"] == "degraded"
    assert payload["evidence_source"]["mode"] == "stale_cache_after_live_failure"
    assert payload["evidence_source"]["live_query_executed"] is False
    assert payload["evidence_source"]["details"]["attempted_live_query"] is True
    assert payload["evidence_source"]["details"]["previous_evidence_source"]["status"] == "live"
    assert payload["evidence_source"]["details"]["retry_after_by_source"] == {"crossref": "5"}
    assert payload["evidence_source"]["reason"] == "RATE_LIMITED"
    assert payload["evidence_source"]["details"]["error_details_by_source"]["crossref"] == {
        "code": "RATE_LIMITED",
        "source": "crossref",
        "status_code": 429,
        "retry_after": "5",
    }
    assert cache_reads == [
        (
            "literature_live_search",
            {"query": "", "doi": "", "pmid": "12345", "max_results": 1},
            {},
        ),
        (
            "literature_live_search",
            {"query": "", "doi": "", "pmid": "12345", "max_results": 1},
            {"allow_stale": True},
        ),
    ]


async def test_literature_live_search_marks_runtime_failure_as_degraded(monkeypatch):
    import app.tools.literature_live_search as literature_module

    cache_reads = []

    async def fake_get_cached_result(namespace, params, **kwargs):
        cache_reads.append((namespace, params, kwargs))
        return None

    async def fake_set_cached_result(*args, **kwargs):
        raise AssertionError("live failure without cache should not be cached")

    class FailingPubMedClient:
        async def search(self, *args, **kwargs):
            raise TimeoutError("pubmed timeout")

        async def close(self):
            return None

    class FailingCrossrefClient:
        async def search(self, *args, **kwargs):
            raise RuntimeError("crossref unavailable")

        async def close(self):
            return None

    monkeypatch.setattr(literature_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(literature_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(literature_module, "PubMedEUtilitiesClient", FailingPubMedClient)
    monkeypatch.setattr(literature_module, "CrossrefClient", FailingCrossrefClient)

    payload = await ToolRegistry.execute(
        "literature_live_search",
        {"pmid": "12345", "max_results": 1},
    )

    assert payload["status"] == "degraded"
    assert payload["results"] == []
    assert payload["errors"]["pubmed"] == "pubmed timeout"
    assert payload["errors"]["crossref"] == "crossref unavailable"
    assert payload["evidence_source"]["status"] == "degraded"
    assert payload["evidence_source"]["mode"] == "live_query_failed"
    assert payload["evidence_source"]["live_query_executed"] is False
    assert payload["evidence_source"]["details"]["attempted_live_query"] is True
    assert cache_reads == [
        (
            "literature_live_search",
            {"query": "", "doi": "", "pmid": "12345", "max_results": 1},
            {},
        ),
        (
            "literature_live_search",
            {"query": "", "doi": "", "pmid": "12345", "max_results": 1},
            {"allow_stale": True},
        ),
    ]


async def test_literature_live_search_keeps_partial_live_failure_as_live(monkeypatch):
    import app.tools.literature_live_search as literature_module

    cache_writes = []

    async def fake_get_cached_result(*args, **kwargs):
        return None

    async def fake_set_cached_result(*args, **kwargs):
        cache_writes.append((args, kwargs))

    class SuccessfulPubMedClient:
        async def search(self, *, query="", doi="", pmid="", max_results=10):
            return [
                {
                    "source": "pubmed",
                    "pmid": "12345",
                    "doi": "10.1000/demo",
                    "title": "PubMed-only enzyme paper",
                    "journal": "Demo Journal",
                    "published": "2025",
                    "authors": ["A Author"],
                    "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
                }
            ]

        async def close(self):
            return None

    class FailingCrossrefClient:
        async def search(self, *args, **kwargs):
            raise RuntimeError("crossref unavailable")

        async def close(self):
            return None

    monkeypatch.setattr(literature_module, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(literature_module, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(literature_module, "PubMedEUtilitiesClient", SuccessfulPubMedClient)
    monkeypatch.setattr(literature_module, "CrossrefClient", FailingCrossrefClient)

    payload = await ToolRegistry.execute(
        "literature_live_search",
        {"query": "enzyme paper", "max_results": 2},
    )

    assert payload["status"] == "completed"
    assert payload["results_count"] == 1
    assert payload["sources_queried"] == ["pubmed"]
    assert payload["errors"] == {"crossref": "crossref unavailable"}
    assert payload["evidence_source"]["status"] == "live"
    assert payload["evidence_source"]["mode"] == "pubmed_crossref_rest"
    assert payload["evidence_source"]["live_query_executed"] is True
    assert payload["evidence_source"]["details"]["partial_errors"] == {
        "crossref": "crossref unavailable"
    }
    assert cache_writes


async def test_literature_live_search_blocks_missing_lookup_input():
    import app.tools.literature_live_search  # noqa: F401 - ensure tool is registered

    payload = await ToolRegistry.execute("literature_live_search", {})

    assert payload["status"] == "blocked"
    assert payload["results_count"] == 0
    assert payload["evidence_source"]["status"] == "blocked"
    assert payload["evidence_source"]["live_query_executed"] is False


async def test_interpro_live_lookup_marks_successful_run_as_live(monkeypatch):
    import app.tools.interpro_live_lookup as interpro_module

    class FakeInterProClient:
        def __init__(self, *args, **kwargs):
            pass

        async def resolve_annotations(self, sequence="", uniprot_id=""):
            return {
                "found": True,
                "query": {"uniprot_id": uniprot_id, "sequence_length": len(sequence) if sequence else 0},
                "summary": {"annotation_count": 1, "raw_record_count": 1, "entry_type_counts": {"Family": 1}},
                "annotations": [
                    {
                        "interpro_id": "IPR001461",
                        "name": "Peptidase A1",
                        "entry_type": "Family",
                        "source": "interpro_live",
                        "regions": [{"start": 70, "end": 320}],
                    }
                ],
                "evidence_source": {
                    "source": "InterPro",
                    "status": "live",
                    "mode": "interpro_api",
                    "live_query_executed": True,
                },
            }

    monkeypatch.setattr(interpro_module, "InterProLiveClient", FakeInterProClient)

    payload = await ToolRegistry.execute(
        "interpro_live_lookup",
        {"uniprot_id": "Q69IF8", "max_results": 5},
    )

    assert payload["status"] == "completed"
    assert payload["found"] is True
    assert payload["results_count"] == 1
    assert payload["results"][0]["interpro_id"] == "IPR001461"
    assert payload["results"][0]["regions"] == [{"start": 70, "end": 320}]
    assert payload["evidence_source"]["status"] == "live"
    assert payload["evidence_source"]["live_query_executed"] is True


async def test_interpro_live_lookup_blocks_sequence_only_input():
    import app.tools.interpro_live_lookup  # noqa: F401 - ensure tool is registered

    payload = await ToolRegistry.execute("interpro_live_lookup", {"sequence": "ACDEFGHIKLMNPQRSTVWY"})

    assert payload["status"] == "blocked"
    assert payload["found"] is False
    assert payload["evidence_source"]["status"] == "blocked"
    assert payload["evidence_source"]["live_query_executed"] is False
    assert "InterProScan" in payload["evidence_source"]["reason"]


async def test_interpro_live_lookup_marks_runtime_failure_as_degraded(monkeypatch):
    import app.tools.interpro_live_lookup as interpro_module

    class FailingInterProClient:
        def __init__(self, *args, **kwargs):
            pass

        async def resolve_annotations(self, sequence="", uniprot_id=""):
            return {
                "found": False,
                "query": {"uniprot_id": uniprot_id, "sequence_length": len(sequence) if sequence else 0},
                "summary": {"annotation_count": 0, "raw_record_count": 0, "entry_type_counts": {}},
                "annotations": [],
                "evidence_source": {
                    "source": "InterPro",
                    "status": "blocked",
                    "mode": "interpro_api",
                    "live_query_executed": True,
                    "reason": "InterPro live query failed: TimeoutError",
                    "details": {"attempted_live_query": True},
                },
            }

    monkeypatch.setattr(interpro_module, "InterProLiveClient", FailingInterProClient)

    payload = await ToolRegistry.execute("interpro_live_lookup", {"uniprot_id": "Q69IF8"})

    assert payload["status"] == "blocked"
    assert payload["results_count"] == 0
    assert payload["evidence_source"]["status"] == "blocked"
    assert payload["evidence_source"]["mode"] == "interpro_api"
    assert payload["evidence_source"]["live_query_executed"] is True
    assert payload["evidence_source"]["details"]["attempted_live_query"] is True


async def test_interproscan_sequence_submit_returns_live_job_id(monkeypatch):
    import app.tools.interproscan_sequence_submit as submit_module

    calls = []

    class FakeResponse:
        text = "iprscan5-R20260804-123456-0000-12345678-p1m"

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, data):
            calls.append((url, data))
            return FakeResponse()

    monkeypatch.setattr(submit_module.httpx, "AsyncClient", FakeAsyncClient)

    payload = await ToolRegistry.execute(
        "interproscan_sequence_submit",
        {
            "sequence": " acd\nefghik ",
            "email": "researcher@example.com",
            "title": "demo job",
        },
    )

    assert payload["status"] == "submitted"
    assert payload["job_id"] == "iprscan5-R20260804-123456-0000-12345678-p1m"
    assert payload["results"] == []
    assert payload["result_available"] is False
    assert payload["evidence_source"]["status"] == "live"
    assert payload["evidence_source"]["live_query_executed"] is True
    assert calls == [
        (
            submit_module.INTERPROSCAN_RUN_ENDPOINT,
            {"sequence": "ACDEFGHIK", "email": "researcher@example.com", "title": "demo job"},
        )
    ]


async def test_interproscan_sequence_submit_blocks_missing_sequence():
    payload = await ToolRegistry.execute(
        "interproscan_sequence_submit",
        {"email": "researcher@example.com", "title": "no sequence"},
    )

    assert payload["status"] == "blocked"
    assert payload["job_id"] is None
    assert payload["results"] == []
    assert payload["result_available"] is False
    assert "No usable InterProScan results" in payload["message"]
    assert payload["evidence_source"]["status"] == "blocked"
    assert payload["evidence_source"]["live_query_executed"] is False


async def test_interproscan_sequence_submit_marks_network_failure_degraded(monkeypatch):
    import app.tools.interproscan_sequence_submit as submit_module

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, data):
            raise submit_module.httpx.ConnectError("network unavailable")

    monkeypatch.setattr(submit_module.httpx, "AsyncClient", FakeAsyncClient)

    payload = await ToolRegistry.execute(
        "interproscan_sequence_submit",
        {"sequence": "ACDEFGHIK", "title": "network failure"},
    )

    assert payload["status"] == "degraded"
    assert payload["job_id"] is None
    assert payload["results"] == []
    assert payload["result_available"] is False
    assert "No usable InterProScan results" in payload["message"]
    assert payload["evidence_source"]["status"] == "degraded"
    assert payload["evidence_source"]["mode"] == "live_submission_failed"
    assert payload["evidence_source"]["live_query_executed"] is False
    assert payload["evidence_source"]["details"]["attempted_live_query"] is True


async def test_interproscan_sequence_status_pending_returns_live_without_results(monkeypatch):
    import app.tools.interproscan_sequence_submit as submit_module

    calls = []

    class FakeResponse:
        text = "RUNNING"

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr(submit_module.httpx, "AsyncClient", FakeAsyncClient)

    payload = await ToolRegistry.execute(
        "interproscan_sequence_status",
        {"job_id": "iprscan5-R20260804-123456-0000-12345678-p1m"},
    )

    assert payload["status"] == "pending"
    assert payload["ebi_status"] == "RUNNING"
    assert payload["result_available"] is False
    assert payload["results"] == []
    assert payload["results_count"] == 0
    assert payload["evidence_source"]["status"] == "live"
    assert payload["evidence_source"]["live_query_executed"] is True
    assert payload["evidence_source"]["details"]["result_polling_executed"] is False
    assert calls == [
        submit_module._job_endpoint(
            submit_module.INTERPROSCAN_STATUS_ENDPOINT,
            "iprscan5-R20260804-123456-0000-12345678-p1m",
        )
    ]


async def test_interproscan_sequence_status_finished_parses_json_results(monkeypatch):
    import app.tools.interproscan_sequence_submit as submit_module

    job_id = "iprscan5-R20260804-123456-0000-12345678-p1m"
    calls = []

    class FakeStatusResponse:
        text = "FINISHED"

        def raise_for_status(self):
            return None

    class FakeJsonResponse:
        text = "{}"

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "matches": [
                            {
                                "signature": {
                                    "accession": "PF00001",
                                    "name": "7tm_1",
                                    "signatureLibraryRelease": {"library": "PFAM", "version": "36.0"},
                                    "entry": {
                                        "accession": "IPR000001",
                                        "name": "Rhodopsin-like GPCR superfamily",
                                        "type": "FAMILY",
                                    },
                                },
                                "locations": [{"start": 12, "end": 245}],
                            }
                        ]
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            calls.append(url)
            if url.endswith(f"/status/{job_id}"):
                return FakeStatusResponse()
            if url.endswith(f"/result/{job_id}/json"):
                return FakeJsonResponse()
            raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(submit_module.httpx, "AsyncClient", FakeAsyncClient)

    payload = await ToolRegistry.execute(
        "interproscan_sequence_status",
        {"job_id": job_id, "max_results": 10},
    )

    assert payload["status"] == "completed"
    assert payload["ebi_status"] == "FINISHED"
    assert payload["result_available"] is True
    assert payload["result_format"] == "json"
    assert payload["results_count"] == 1
    result = payload["results"][0]
    assert result["interpro_accession"] == "IPR000001"
    assert result["name"] == "Rhodopsin-like GPCR superfamily"
    assert result["entry_type"] == "FAMILY"
    assert result["start"] == 12
    assert result["end"] == 245
    assert result["signature_accession"] == "PF00001"
    assert result["signature_database"] == "PFAM"
    assert result["signature"]["database"] == "PFAM"
    assert payload["evidence_source"]["status"] == "live"
    assert calls == [
        submit_module._job_endpoint(submit_module.INTERPROSCAN_STATUS_ENDPOINT, job_id),
        submit_module._result_endpoint(job_id, "json"),
    ]


async def test_interproscan_sequence_status_blocks_missing_job_id():
    payload = await ToolRegistry.execute("interproscan_sequence_status", {})

    assert payload["status"] == "blocked"
    assert payload["job_id"] is None
    assert payload["result_available"] is False
    assert payload["results"] == []
    assert payload["evidence_source"]["status"] == "blocked"
    assert payload["evidence_source"]["live_query_executed"] is False
    assert "MISSING_JOB_ID" in payload["evidence_source"]["reason"]


async def test_interproscan_sequence_status_marks_network_failure_degraded(monkeypatch):
    import app.tools.interproscan_sequence_submit as submit_module

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            raise submit_module.httpx.ConnectError("network unavailable")

    monkeypatch.setattr(submit_module.httpx, "AsyncClient", FakeAsyncClient)

    payload = await ToolRegistry.execute(
        "interproscan_sequence_status",
        {"job_id": "iprscan5-R20260804-123456-0000-12345678-p1m"},
    )

    assert payload["status"] == "degraded"
    assert payload["result_available"] is False
    assert payload["results"] == []
    assert payload["evidence_source"]["status"] == "degraded"
    assert payload["evidence_source"]["mode"] == "interproscan_rest_poll_failed"
    assert payload["evidence_source"]["live_query_executed"] is False
    assert payload["evidence_source"]["details"]["attempted_live_query"] is True
