#!/usr/bin/env python3
"""Refresh numbering-review data products for human review.

This script is audit-only. It rebuilds the EC-confirmed enzyme numbering
review queue, packets, semantic conflict queue, dashboard, and human decision
backlog so the review UI can show current data without changing reviewed
decisions.
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path


AI_ROOT = Path(__file__).resolve().parents[1]

COMMANDS = [
    ["python3", "scripts/build_numbering_enzyme_fireprot_queue.py"],
    ["python3", "scripts/build_numbering_review_packets.py"],
    ["python3", "scripts/build_numbering_review_briefing.py"],
    ["python3", "scripts/build_numbering_review_briefing_status_board.py"],
    ["python3", "scripts/build_numbering_decision_semantic_conflict_queue.py"],
    ["python3", "scripts/build_numbering_review_operator_queue.py"],
    ["python3", "scripts/build_human_decision_backlog.py"],
    ["python3", "scripts/build_curation_dashboard.py"],
]


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=AI_ROOT, check=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh numbering review data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run:
        for command in COMMANDS:
            run(command)

    print(
        {
            "ok": True,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "commands": COMMANDS,
            "safe_for_model_claim": False,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
