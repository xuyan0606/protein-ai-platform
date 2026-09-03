"""P0 requested mutation review regressions."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _tool_result(tool_name: str, payload: dict) -> dict:
    return {"tool_name": tool_name, "status": "completed", "result": json.dumps(payload, ensure_ascii=False)}


def test_requested_mutation_review_handles_feedback_tradeoff_without_new_candidate_table():
    from app.core.agent_graph import AgentOrchestrator

    report = AgentOrchestrator._build_requested_mutation_review_report(
        "P338T 实验比活提高 30%，稳定性下降 40%，你重新分析这个突变。",
        [
            _tool_result(
                "mutation_priority_score",
                {
                    "candidate_table_status": "ready",
                    "experiment_design_table": [
                        {
                            "position": 338,
                            "recommended_mutations": [{"mutation": "P338T"}],
                            "mutation_logic": "loop gate flexibility hypothesis",
                            "expected_effect": "activity-stability trade-off",
                            "experiment_priority": "P2",
                        }
                    ],
                },
            ),
            _tool_result(
                "rosetta_ddg",
                {
                    "status": "completed",
                    "is_real_rosetta": False,
                    "evidence_level": "local_heuristic_estimate",
                    "results": [
                        {"mutation": "P338T", "ddg_kcal_mol": 1.8, "ddg_label": "destabilizing"}
                    ],
                },
            ),
        ],
    )

    assert "# 指定突变复核" in report
    assert "P338T" in report
    assert "Pro->Thr" in report
    assert "activity-stability trade-off" in report
    assert "保留活性收益假设" in report
    assert "不要直接回退该突变" in report
    assert "不声明确定提升" in report


def test_requested_mutation_review_blocks_protected_position_and_marks_unknown_features():
    from app.core.agent_graph import AgentOrchestrator

    report = AgentOrchestrator._build_requested_mutation_review_report(
        "请复核 D80N 这个突变怎么样。",
        [
            _tool_result(
                "enzyme_identity_profile",
                {
                    "identity_status": "identified",
                    "protected_positions": [80],
                },
            )
        ],
    )

    assert "当前决策**：No-Go" in report
    assert "D80N" in report
    assert "protected" in report
    assert "命中保护位点" in report
    assert "relSASA、pocket/channel、到催化簇距离和保守性字段只能标为 unknown" in report


def test_synthesize_prefers_requested_mutation_review_before_no_evidence_reply():
    from app.core.agent_graph import AgentOrchestrator

    orch = AgentOrchestrator()
    report = __import__("asyncio").run(
        orch._synthesize_sc(
            "这个突变 A10V 怎么样？",
            [],
            research="",
            history=[],
        )
    )

    assert "# 指定突变复核" in report
    assert "A10V" in report
    assert "本轮没有完成的位点级工具证据" in report
    assert "不声明确定提升" in report
