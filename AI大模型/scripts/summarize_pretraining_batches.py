#!/usr/bin/env python3
"""Summarize completed sequence pretraining batch receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize sequence pretraining batches")
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for path in sorted(args.report_dir.glob("sequence_mlm_batch_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = Path(data.get("checkpoint_path", ""))
        rows.append({
            "report": str(path.resolve()),
            "batch": path.stem.removeprefix("sequence_mlm_batch_"),
            "status": data.get("status"),
            "sequence_count": data.get("sequence_count", 0),
            "steps": data.get("steps", 0),
            "final_loss": data.get("final_loss"),
            "validation_loss": data.get("validation_loss"),
            "checkpoint": str(checkpoint.resolve()),
            "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest() if checkpoint.exists() else None,
        })
    payload = {
        "artifact_kind": "unlabeled_sequence_pretraining_batch_summary",
        "completed_batch_count": sum(row["status"] == "completed_pretraining_only" for row in rows),
        "rows": rows,
        "safe_for_supervised_training": False,
        "safe_for_model_claim": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"completed_batch_count": payload["completed_batch_count"], "report_count": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
