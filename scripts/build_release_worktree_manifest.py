#!/usr/bin/env python3
"""Build a path-only manifest of the dirty release worktree."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "manuals" / "release-worktree-manifest-2026-08-17.json"


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def build_manifest() -> dict[str, Any]:
    revision = _run_git(["rev-parse", "--short", "HEAD"])
    status_lines = _run_git(["status", "--short"]).splitlines()
    files = []
    counts: Counter[str] = Counter()
    for line in status_lines:
        if not line:
            continue
        status = line[:2]
        path = line[3:] if len(line) > 3 else ""
        counts[status.strip() or status] += 1
        files.append({"status": status, "path": path})
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_release_worktree_manifest",
        "network_io": "not_executed",
        "destructive_actions": "not_executed",
        "secrets_printed": False,
        "revision": revision,
        "dirty": bool(files),
        "dirty_file_count": len(files),
        "counts_by_status": dict(sorted(counts.items())),
        "files": files,
        "summary": {
            "status": "manual_required" if files else "clean",
            "detail": "dirty worktree must be reviewed before production deployment" if files else "worktree clean",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    manifest = build_manifest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = {
        "status": manifest["summary"]["status"],
        "dirty": manifest["dirty"],
        "dirty_file_count": manifest["dirty_file_count"],
        "output": str(output),
        "network_io": manifest["network_io"],
        "destructive_actions": manifest["destructive_actions"],
        "secrets_printed": manifest["secrets_printed"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"summary\t{summary['status']}\tdirty_file_count={summary['dirty_file_count']}")
        print(f"output\t{summary['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
