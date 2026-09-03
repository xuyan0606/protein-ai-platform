#!/usr/bin/env python3
"""Build a read-only preview of explicitly approved MSA gap decisions."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_msa_gap_review_decisions import build_approved_preview, load_jsonl, QUEUE, DECISIONS
ROOT = Path(__file__).resolve().parents[1]
def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--queue", type=Path, default=QUEUE); p.add_argument("--decisions", type=Path, default=DECISIONS); p.add_argument("--output", type=Path, default=ROOT / "reports/msa_gap_approved_preview.json"); a = p.parse_args()
    out = build_approved_preview(load_jsonl(a.queue), load_jsonl(a.decisions)); a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(json.dumps(out, ensure_ascii=False)); return 0
if __name__ == "__main__": raise SystemExit(main())
