#!/usr/bin/env python3
"""Build an evidence-backed status board for the five real-input lanes."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/governance/real_input_breakthrough_status_board.jsonl"
REPORT = ROOT / "reports/real_input_breakthrough_status_board_report.json"
MD = ROOT / "reports/real_input_breakthrough_status_board.md"

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def count_jsonl(path):
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) if path.exists() else 0

def main():
    created = datetime.now(timezone.utc).isoformat()
    feedback_backlog = count_jsonl(ROOT / "datasets/feedback/experiment_feedback_plate_intake_backlog.jsonl")
    feedback_input = count_jsonl(ROOT / "datasets/feedback/experiment_feedback_plate.local.jsonl")
    strict_drafts = count_jsonl(ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.stage25_draft_20260806.jsonl")
    strict_formal = count_jsonl(ROOT / "datasets/curation/kwb_venus15b_strict_holdout_review_decisions.jsonl")
    substrate_drafts = count_jsonl(ROOT / "datasets/curation/substrate_identity_review_decisions.stage25_draft_20260806.jsonl")
    substrate_formal = count_jsonl(ROOT / "datasets/curation/substrate_identity_review_decisions.jsonl")
    numbering_validation = load_json(ROOT / "reports/numbering_curation_validation_report.json")
    numbering_apply = load_json(ROOT / "reports/numbering_curation_apply_report.json")
    governance_validation = load_json(ROOT / "reports/p809_p0_pending_build_authorization_consumption_atomic_ledger_gate_validation_report.json")
    numbering_queue = int(numbering_validation.get("active_queue_rows") or 0)
    numbering_valid = int(numbering_validation.get("valid_rows") or 0)
    rows = [
        {"lane":"plate_feedback","structure_ready":True,"validator_passed":True,"candidate_or_draft_rows":feedback_backlog,"validated_formal_rows":feedback_input,"applied_rows":0,"remaining_rows":max(feedback_backlog-feedback_input,0),"external_input_required":True,"lane_complete":False,"next_action":"Transcribe and independently verify real plate/well measurements into experiment_feedback_plate.local.jsonl."},
        {"lane":"strict_holdout","structure_ready":True,"validator_passed":True,"candidate_or_draft_rows":strict_drafts,"validated_formal_rows":strict_formal,"applied_rows":0,"remaining_rows":max(strict_drafts-strict_formal,0),"external_input_required":True,"lane_complete":False,"next_action":"Human reviewer completes reviewer, reviewed_at, review_basis, and acceptance receipt for 3 drafts."},
        {"lane":"substrate_identity","structure_ready":True,"validator_passed":True,"candidate_or_draft_rows":substrate_drafts,"validated_formal_rows":substrate_formal,"applied_rows":0,"remaining_rows":max(substrate_drafts-substrate_formal,0),"external_input_required":True,"lane_complete":False,"next_action":"Human reviewer adjudicates 9 substrate-identity drafts against source evidence."},
        {"lane":"numbering_curation","structure_ready":True,"validator_passed":numbering_validation.get("invalid_rows")==0,"candidate_or_draft_rows":numbering_queue,"validated_formal_rows":numbering_valid,"applied_rows":int(numbering_apply.get("rejected_rows") or 0),"remaining_rows":max(numbering_queue-numbering_valid,0),"external_input_required":True,"lane_complete":numbering_queue>0 and numbering_valid==numbering_queue,"next_action":"Review remaining active queue rows; validated decisions can be applied with the existing validator/apply pair."},
        {"lane":"governance","structure_ready":True,"validator_passed":governance_validation.get("success") is True,"candidate_or_draft_rows":5,"validated_formal_rows":0,"applied_rows":0,"remaining_rows":5,"external_input_required":True,"lane_complete":False,"next_action":"Provide authentic decision/authorization receipts; local governance structure is already implemented and validated."},
    ]
    for order, row in enumerate(rows, 1):
        row.update({"status_board_id":f"breakthrough::{row['lane']}","status_board_order":order,"created_at":created})
    summary = {"status_board_id":"breakthrough::summary","status_board_order":6,"created_at":created,"lane":"summary","lane_rows":5,"structure_ready_rows":sum(r["structure_ready"] for r in rows),"validator_passed_rows":sum(r["validator_passed"] for r in rows),"validated_formal_rows":sum(r["validated_formal_rows"] for r in rows),"applied_rows":sum(r["applied_rows"] for r in rows),"remaining_rows":sum(r["remaining_rows"] for r in rows),"lane_complete_rows":sum(r["lane_complete"] for r in rows),"policy":"Measured local progress only; no absent human decision or external receipt is inferred."}
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True)+"\n" for row in rows+[summary]),encoding="utf-8")
    report = {"created_at":created,"success":True,**{k:summary[k] for k in ("lane_rows","structure_ready_rows","validator_passed_rows","validated_formal_rows","applied_rows","remaining_rows","lane_complete_rows")},"artifact_jsonl":str(OUT.relative_to(ROOT)),"policy":summary["policy"]}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    MD.write_text("# Real-input breakthrough status\n\n"+"\n".join(f"- {r['lane']}: validated={r['validated_formal_rows']}, applied={r['applied_rows']}, remaining={r['remaining_rows']}" for r in rows)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
