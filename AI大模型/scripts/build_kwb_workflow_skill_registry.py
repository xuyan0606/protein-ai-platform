#!/usr/bin/env python3
"""Build local KWB workflow skill registry and Markdown skill files."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = AI_ROOT / "platform_integration" / "workflow_skills"
JSONL_OUT = AI_ROOT / "datasets" / "governance" / "kwb_workflow_skill_registry.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "kwb_workflow_skill_registry_report.json"


SKILLS: list[dict[str, Any]] = [
    {
        "skill_id": "enzyme_mutation_prioritization",
        "title": "酶突变优先级分析",
        "path": "platform_integration/workflow_skills/enzyme_mutation_prioritization.md",
        "required_inputs": ["protein_sequence_or_id", "candidate_mutations", "reviewed_numbering_status", "feature_refs"],
        "ordered_steps": [
            "检查 reviewed numbering 和 protected catalytic no-go",
            "读取 validated feature index 中的 MSA/structure/domain input-only 特征",
            "汇总 stability/activity/substrate/assay 风险证据",
            "输出人工复核候选，不写 formal decision",
        ],
        "output_artifacts": ["mutation_prioritization_review_packet.json"],
        "validators": ["scripts/validate_advanced_model_feature_contract_report.py", "scripts/validate_model_quality_hard_gate_contract.py"],
    },
    {
        "skill_id": "ddg_backend_runtime_probe",
        "title": "ddG 后端探测与 smoke",
        "path": "platform_integration/workflow_skills/ddg_backend_runtime_probe.md",
        "required_inputs": ["backend_name", "runtime_path", "license_receipt", "smoke_case"],
        "ordered_steps": [
            "执行 license/config 路径检查",
            "执行 executable/module probe",
            "执行最小 smoke case 并写 receipt",
            "只在 validator 通过后更新 staging 状态",
        ],
        "output_artifacts": ["ddg_runtime_probe_receipt.json"],
        "validators": ["scripts/build_ddg_executable_probe.py", "scripts/validate_ddg_backend_runtime_receipts.py"],
    },
    {
        "skill_id": "wet_lab_feedback_intake_review",
        "title": "湿实验反馈授权导入审核",
        "path": "platform_integration/workflow_skills/wet_lab_feedback_intake_review.md",
        "required_inputs": ["wet_lab_candidate_rows", "source_file_receipt", "metric_unit", "authorization_decision"],
        "ordered_steps": [
            "核实来源、突变编号、单位、重复和批次",
            "区分 qualitative feedback 与 numeric training import",
            "生成 preflight，不直接写训练表",
            "运行授权 validator 和 apply-plan builder",
        ],
        "output_artifacts": ["wet_lab_feedback_authorization_receipt.json"],
        "validators": ["scripts/validate_wet_lab_mutant_library_feedback_authorizations.py", "scripts/build_wet_lab_mutant_library_feedback_preflight.py"],
    },
    {
        "skill_id": "numbering_review_formalization",
        "title": "编号人工审核正式化",
        "path": "platform_integration/workflow_skills/numbering_review_formalization.md",
        "required_inputs": ["queue_row", "evidence_source", "reviewer_decision", "correction_if_wrong"],
        "ordered_steps": [
            "从 UI 或 packet 查看 WT/突变位点/证据",
            "正确则写 accept，错误则写 corrected_position 与 notes",
            "运行 validate_numbering_curation_decisions",
            "运行 apply_numbering_curation，但训练 gate 继续另行判断",
        ],
        "output_artifacts": ["numbering_curation_decision.jsonl"],
        "validators": ["scripts/validate_numbering_curation_decisions.py", "scripts/apply_numbering_curation.py"],
    },
    {
        "skill_id": "five_head_model_gate_review",
        "title": "五头模型训练门控复核",
        "path": "platform_integration/workflow_skills/five_head_model_gate_review.md",
        "required_inputs": ["training_label_import_contract", "wet_lab_authorization_contract", "benchmark_coverage", "physics_ddg_state"],
        "ordered_steps": [
            "检查五个 head 的 training-import-eligible rows",
            "检查 benchmark ready_for_model_claim",
            "检查 physics ddG 是否为 Rosetta/PyRosetta/FoldX 真实后端",
            "输出 model-quality hard-gate 状态，不训练、不声明",
        ],
        "output_artifacts": ["five_head_gate_review_report.json"],
        "validators": ["scripts/validate_five_head_training_execution_contract_report.py", "scripts/validate_model_quality_hard_gate_contract.py"],
    },
]


def markdown_for(skill: dict[str, Any]) -> str:
    steps = "\n".join(f"{idx}. {step}" for idx, step in enumerate(skill["ordered_steps"], start=1))
    inputs = "\n".join(f"- `{item}`" for item in skill["required_inputs"])
    outputs = "\n".join(f"- `{item}`" for item in skill["output_artifacts"])
    validators = "\n".join(f"- `{item}`" for item in skill["validators"])
    return f"""# {skill['title']}

来源：ProteinMCP workflow skill 模式的 KWB 本地化版本。

## 输入

{inputs}

## 步骤

{steps}

## 输出

{outputs}

## Validator

{validators}

## 禁止动作

- 不写训练标签。
- 不写 production 配置。
- 不把工具分数当真实湿实验标签。
- 不把草稿或 UI 选择自动提升为 formal reviewed decision。
- `safe_for_model_claim=false` 和 `release_ready=false` 由硬门槛统一控制。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KWB workflow skill registry")
    parser.add_argument("--jsonl-output", type=Path, default=JSONL_OUT)
    parser.add_argument("--report-output", type=Path, default=REPORT_OUT)
    parser.add_argument("--skill-dir", type=Path, default=SKILL_DIR)
    args = parser.parse_args()

    args.skill_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for skill in SKILLS:
        path = AI_ROOT / skill["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown_for(skill), encoding="utf-8")
        rows.append({
            **skill,
            "borrowed_pattern": "ProteinMCP workflow skill as fixed operator procedure",
            "skill_file_exists": path.exists(),
            "requires_receipt": True,
            "requires_validator": True,
            "writes_training_labels": False,
            "writes_formal_decisions_without_human": False,
            "production_execution_allowed": False,
            "safe_for_training_import": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        })

    args.jsonl_output.parent.mkdir(parents=True, exist_ok=True)
    args.jsonl_output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "skill_rows": len(rows),
        "skill_files_written": sum(1 for row in rows if row["skill_file_exists"]),
        "production_execution_allowed_rows": 0,
        "training_write_allowed_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "jsonl_path": str(args.jsonl_output.relative_to(AI_ROOT)),
        "skill_dir": str(args.skill_dir.relative_to(AI_ROOT)),
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"skill_rows": len(rows), "skill_files_written": report["skill_files_written"], "output": str(args.report_output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
