"""Create a conservative human-review packet for unresolved domain rows."""

import argparse
import json
from pathlib import Path


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_packet(curated_path: Path, evidence_path: Path):
    curated = {r.get("domain_record_id"): r for r in _jsonl(curated_path)}
    evidence = {r.get("domain_record_id"): r for r in _jsonl(evidence_path)}
    rows = []
    for record_id, row in sorted(curated.items()):
        if row.get("curation_status") != "domain_interval_unresolved":
            continue
        ev = evidence.get(record_id, {})
        rows.append({
            "domain_record_id": record_id,
            "uniprot_id": ev.get("uniprot_id", row.get("uniprot_id")),
            "pfam_id": ev.get("pfam_id", row.get("pfam_id")),
            "sequence_length": row.get("sequence_length"),
            "other_pfam_ids": ev.get("other_pfam_ids", []),
            "matched_pfam_intervals": ev.get("matched_pfam_intervals", []),
            "recommended_decision": "keep_unresolved",
            "manual_review_required": True,
            "training_authorized": False,
            "notes": "No exact target Pfam interval in current InterPro evidence; require independent HMMER/UniProt/manual review before any interval is set.",
        })
    return {
        "status": "blocked_pending_human_review" if rows else "clear",
        "rows": rows,
        "row_count": len(rows),
        "training_authorized": False,
        "model_claim_authorized": False,
        "policy": "unresolved domain rows remain excluded from domain-relative training features until reviewed decision is recorded",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--curated", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    out = build_packet(a.curated, a.evidence)
    a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "row_count": out["row_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
