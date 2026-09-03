#!/usr/bin/env python3
"""Build human-review packets for the two remaining KWB hard gates.

The packet is an evidence view, not a decision.  Formal decisions are kept in
separate JSONL files and remain empty until a human reviewer supplies the
decision, receipt, and review metadata.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
STRICT_INPUT = AI_ROOT / "cache/advanced_features/benchmarks/kwb_venus15b_strict_holdout_candidate/dataset.jsonl"
SUBSTRATE_INPUT = AI_ROOT / "datasets/curation/substrate_identity_evidence_candidates.jsonl"
STRICT_PACKETS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_packets.jsonl"
SUBSTRATE_PACKETS = AI_ROOT / "datasets/curation/substrate_identity_review_packets.jsonl"
STRICT_DECISIONS = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl"
SUBSTRATE_DECISIONS = AI_ROOT / "datasets/curation/substrate_identity_review_decisions.jsonl"
STRICT_TEMPLATE = AI_ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.template.jsonl"
SUBSTRATE_TEMPLATE = AI_ROOT / "datasets/curation/substrate_identity_review_decisions.template.jsonl"
REPORT = AI_ROOT / "reports/hard_gate_review_packet_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def rel(path: Path) -> str:
    return str(path.relative_to(AI_ROOT))


def strict_packet(row: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {
        "packet_id": f"kwb-venus15b-strict-review-{ordinal:03d}",
        "packet_type": "kwb_strict_mutation_holdout_review",
        "review_key": row.get("benchmark_record_id"),
        "project_id": row.get("project_id"),
        "variant": row.get("variant"),
        "mutation": row.get("mutation"),
        "wild_type": row.get("wild_type"),
        "canonical_position": row.get("canonical_position"),
        "mutant": row.get("mutant"),
        "sequence_residue": row.get("sequence_residue"),
        "pdb_chain": row.get("pdb_chain"),
        "pdb_residue": row.get("pdb_residue"),
        "sequence_pdb_cross_check": {
            "sequence_verified": row.get("numbering_verified_by_sequence") is True,
            "pdb_verified": row.get("numbering_verified_by_pdb") is True,
            "exact_match": row.get("numbering_cross_check_passed") is True,
        },
        "candidate_label": row.get("candidate_label"),
        "project_overall_judgement": row.get("project_overall_judgement"),
        "measurement_evidence_rows": row.get("measurement_evidence_rows") or [],
        "source_receipts": row.get("source_receipts") or {},
        "required_human_checks": [
            "确认变体确实来自 Venus-15B 真实实验，而不是项目设计或预测结果",
            "确认序列位置、PDB chain A 位置和 WT 残基一致",
            "逐条检查 measurement、batch/control、单位和实验条件",
            "确认该变体不与训练集或其他 benchmark split 泄漏",
            "确认是否允许进入 KWB strict mutation holdout；不确定就 needs_more_info",
        ],
        "allowed_decisions": ["approve_strict_holdout", "reject_candidate", "needs_more_info"],
        "decision_input": rel(STRICT_DECISIONS),
        "formal_decision": None,
        "review_status": "pending_human_review",
        "strict_holdout_eligible_now": False,
        "training_import_eligible_now": False,
        "safe_for_model_claim": False,
        "policy": "Evidence packet only. It never writes a strict row, training label, score, or model claim.",
    }


def substrate_packet(row: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {
        "packet_id": f"substrate-identity-review-{ordinal:03d}",
        "packet_type": "reviewed_substrate_identity_review",
        "review_key": row.get("candidate_id"),
        "candidate_id": row.get("candidate_id"),
        "substrate_identity_normalized": row.get("substrate_identity_normalized"),
        "substrate_name_source_text": row.get("substrate_name_source_text"),
        "substrate_smiles": row.get("substrate_smiles"),
        "smiles_status": row.get("smiles_status"),
        "smiles_blocker": row.get("smiles_blocker"),
        "source_file": row.get("source_file"),
        "source_file_sha256": row.get("source_file_sha256"),
        "source_format": row.get("source_format"),
        "evidence_paragraphs": row.get("evidence_paragraphs") or [],
        "protocol_numeric_evidence": row.get("protocol_numeric_evidence") or {},
        "assay_context": row.get("assay_context") or {},
        "required_human_checks": [
            "确认原文明确写的是这个底物或工艺体系，不是从酶活名称猜出来的",
            "确认它是单一化合物还是工艺混合物；混合物不能硬填单分子 SMILES",
            "确认底物范围、工艺阶段、pH/温度/时间和 protocol 版本",
            "确认该身份能否作为 substrate_fit 的评测或训练标签语义",
            "证据不完整就 needs_more_info，不要用 generic activity 代替",
        ],
        "allowed_decisions": [
            "approve_reviewed_substrate_identity",
            "reject_substrate_identity",
            "needs_more_info",
        ],
        "decision_input": rel(SUBSTRATE_DECISIONS),
        "formal_decision": None,
        "review_status": "pending_human_review",
        "candidate_for_reviewed_substrate_identity_set": False,
        "substrate_fit_label_eligible_now": False,
        "safe_for_model_claim": False,
        "policy": "Evidence packet only. It never invents SMILES, approves identity, writes labels, or opens a claim gate.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build hard-gate human review packets")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    strict_candidates = load_jsonl(STRICT_INPUT)
    substrate_candidates = load_jsonl(SUBSTRATE_INPUT)
    strict_rows = [strict_packet(row, index) for index, row in enumerate(strict_candidates, start=1)]
    substrate_rows = [substrate_packet(row, index) for index, row in enumerate(substrate_candidates, start=1)]
    write_jsonl(STRICT_PACKETS, strict_rows)
    write_jsonl(SUBSTRATE_PACKETS, substrate_rows)

    write_jsonl(STRICT_TEMPLATE, [{
        "review_key": "<benchmark_record_id>",
        "decision": "needs_more_info",
        "source_evidence_confirmed": False,
        "numbering_confirmed": False,
        "wetlab_result_confirmed": False,
        "leakage_check_passed": False,
        "approved_label": None,
        "acceptance_receipt": None,
        "review_basis": "",
        "reviewer": "",
        "reviewed_at": "",
        "notes": "",
        "policy": "Template only. Copy a completed row to the formal decision file only after human review.",
    }])
    write_jsonl(SUBSTRATE_TEMPLATE, [{
        "review_key": "<candidate_id>",
        "decision": "needs_more_info",
        "identity_confirmed": False,
        "representation_type": None,
        "scope_confirmed": False,
        "condition_confirmed": False,
        "protocol_version_confirmed": False,
        "substrate_smiles": None,
        "acceptance_receipt": None,
        "review_basis": "",
        "reviewer": "",
        "reviewed_at": "",
        "notes": "",
        "policy": "Template only. Do not infer SMILES or copy into a formal decision without human review.",
    }])

    strict_decisions = load_jsonl(STRICT_DECISIONS)
    substrate_decisions = load_jsonl(SUBSTRATE_DECISIONS)
    for decision_path in (STRICT_DECISIONS, SUBSTRATE_DECISIONS):
        if not decision_path.exists():
            decision_path.parent.mkdir(parents=True, exist_ok=True)
            decision_path.write_text("", encoding="utf-8")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strict_candidate_rows": len(strict_candidates),
        "strict_packet_rows": len(strict_rows),
        "strict_formal_decision_rows": len(strict_decisions),
        "substrate_candidate_rows": len(substrate_candidates),
        "substrate_packet_rows": len(substrate_rows),
        "substrate_formal_decision_rows": len(substrate_decisions),
        "strict_holdout_rows_written": 0,
        "substrate_fit_training_rows_written": 0,
        "training_import_written_rows": 0,
        "safe_for_model_claim": False,
        "release_ready": False,
        "artifacts": {
            "strict_packets": rel(STRICT_PACKETS),
            "strict_template": rel(STRICT_TEMPLATE),
            "substrate_packets": rel(SUBSTRATE_PACKETS),
            "substrate_template": rel(SUBSTRATE_TEMPLATE),
            "strict_decisions": rel(STRICT_DECISIONS),
            "substrate_decisions": rel(SUBSTRATE_DECISIONS),
        },
        "policy": "Packets are real source-traced review work, but no formal human decision is inferred.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "strict_packet_rows": len(strict_rows),
        "substrate_packet_rows": len(substrate_rows),
        "strict_formal_decision_rows": len(strict_decisions),
        "substrate_formal_decision_rows": len(substrate_decisions),
        "output": rel(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
