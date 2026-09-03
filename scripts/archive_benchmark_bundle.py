#!/usr/bin/env python3
"""Archive a benchmark deploy bundle into a tar.gz package.

Example:
  python3 scripts/archive_benchmark_bundle.py --case-id venus-15b
"""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "benchmark_cases"


def _load_case(case_id: str) -> dict[str, object]:
    fixture = FIXTURE_ROOT / f"{case_id.replace('-', '_')}.json"
    if not fixture.exists():
        raise SystemExit(f"Benchmark fixture not found: {fixture}")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid fixture JSON: {fixture}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True, help="Benchmark case id, e.g. venus-15b")
    args = parser.parse_args()

    case = _load_case(args.case_id)
    paths = case.get("paths")
    if not isinstance(paths, dict):
        raise SystemExit("Fixture missing 'paths'")

    bundle_dir = PROJECT_ROOT / str(paths.get("deploy_bundle_dir", ""))
    archive_file = PROJECT_ROOT / str(paths.get("deploy_bundle_archive_file", ""))
    if not bundle_dir.exists():
        raise SystemExit(f"Bundle directory not found: {bundle_dir}")
    archive_file.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_file, "w:gz") as tar:
        tar.add(bundle_dir, arcname=bundle_dir.name)

    print(f"Archived bundle: {archive_file}")
    print(f"Bundle source: {bundle_dir}")
    print(f"Archive size bytes: {archive_file.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
