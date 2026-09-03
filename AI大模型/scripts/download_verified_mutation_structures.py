#!/usr/bin/env python3
"""Download selected public PDB files for verified mutation structure candidates."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
INPUT = AI_ROOT / "datasets" / "curation" / "verified_mutation_structure_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "verified_mutation_structure_download_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else AI_ROOT / path


def download_gzip(url: str, destination: Path, timeout: int) -> None:
    tmp_gz = destination.with_suffix(".pdb.download.gz")
    tmp_pdb = destination.with_suffix(".pdb.download")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            with tmp_gz.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        with gzip.open(tmp_gz, "rb") as source, tmp_pdb.open("wb") as destination_handle:
            shutil.copyfileobj(source, destination_handle)
        if tmp_pdb.stat().st_size == 0:
            raise RuntimeError("downloaded PDB is empty")
        tmp_pdb.replace(destination)
    finally:
        for path in (tmp_gz, tmp_pdb):
            if path.exists():
                path.unlink()


def cache_path(structure_id: str) -> Path:
    return AI_ROOT / "cache" / "structures" / "verified_mutations" / "pdb" / f"{structure_id.lower()}.pdb"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download verified-mutation candidate PDB files")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=INPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--limit", type=int, default=0, help="Maximum unique PDB ids; 0 means all")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    processed_ids: set[str] = set()
    downloaded_ids: set[str] = set()
    existing_ids: set[str] = set()
    failed: dict[str, str] = {}
    resolved_by_requested: dict[str, str] = {}
    for row in rows:
        requested_structure_id = str(row.get("structure_id") or "")
        destination = resolve(str(row.get("expected_cache_path") or ""))
        if requested_structure_id in resolved_by_requested:
            resolved_structure_id = resolved_by_requested[requested_structure_id]
            row["requested_structure_id"] = requested_structure_id
            row["fallback_structure_id"] = resolved_structure_id
            row["fallback_index"] = 1
            row["structure_id"] = resolved_structure_id
            row["download_url"] = f"https://files.rcsb.org/download/{resolved_structure_id}.pdb.gz"
            destination = cache_path(resolved_structure_id)
            row["expected_cache_path"] = str(destination.relative_to(AI_ROOT))
        if requested_structure_id in failed:
            row["acquisition_status"] = "download_failed"
            row["download_error"] = failed[requested_structure_id]
            continue
        if destination.exists() and destination.stat().st_size > 0:
            row["actual_cache_path"] = str(destination.relative_to(AI_ROOT))
            row["structure_sha256"] = sha256(destination)
            row["acquisition_status"] = "already_present"
            existing_ids.add(requested_structure_id)
            continue
        if requested_structure_id not in processed_ids:
            if args.limit and len(processed_ids) >= args.limit:
                continue
            processed_ids.add(requested_structure_id)
            if args.dry_run:
                row["acquisition_status"] = "download_planned"
                continue
            attempts = [requested_structure_id, *[str(item).upper() for item in row.get("fallback_structure_ids") or []]]
            errors: list[str] = []
            resolved_structure_id = None
            for fallback_index, structure_id in enumerate(attempts):
                fallback_destination = cache_path(structure_id)
                if fallback_destination.exists() and fallback_destination.stat().st_size > 0:
                    resolved_structure_id = structure_id
                    destination = fallback_destination
                    existing_ids.add(structure_id)
                    if fallback_index:
                        resolved_by_requested[requested_structure_id] = structure_id
                    break
                try:
                    download_gzip(
                        f"https://files.rcsb.org/download/{structure_id}.pdb.gz",
                        fallback_destination,
                        args.timeout,
                    )
                    resolved_structure_id = structure_id
                    destination = fallback_destination
                    downloaded_ids.add(structure_id)
                    if fallback_index:
                        row["requested_structure_id"] = requested_structure_id
                        row["fallback_structure_id"] = structure_id
                        row["fallback_index"] = fallback_index
                        resolved_by_requested[requested_structure_id] = structure_id
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, OSError, RuntimeError) as exc:
                    errors.append(f"{structure_id}: {type(exc).__name__}: {exc}")
            if resolved_structure_id is None:
                failed[requested_structure_id] = "; ".join(errors)
                row["acquisition_status"] = "download_failed"
                row["download_error"] = failed[requested_structure_id]
                continue
            if args.sleep:
                time.sleep(args.sleep)
            if resolved_structure_id != requested_structure_id:
                row["structure_id"] = resolved_structure_id
                row["download_url"] = f"https://files.rcsb.org/download/{resolved_structure_id}.pdb.gz"
                row["expected_cache_path"] = str(destination.relative_to(AI_ROOT))
        if destination.exists() and destination.stat().st_size > 0:
            row["actual_cache_path"] = str(destination.relative_to(AI_ROOT))
            row["structure_sha256"] = sha256(destination)
            row["acquisition_status"] = "downloaded_public_rcsb"

    write_jsonl(args.output, rows)
    report = {
        "input_rows": len(rows),
        "unique_structure_rows": len({str(row.get("structure_id") or "") for row in rows}),
        "downloaded_unique_structures": len(downloaded_ids),
        "already_present_unique_structures": len(existing_ids),
        "failed_unique_structures": len(failed),
        "candidate_rows_with_local_structure": sum(
            1 for row in rows if row.get("acquisition_status") in {"already_present", "downloaded_public_rcsb"}
        ),
        "failures": [{"structure_id": key, "reason": value} for key, value in sorted(failed.items())],
        "dry_run": args.dry_run,
        "output": str(args.output.relative_to(AI_ROOT)),
        "safe_for_model_claim": False,
        "policy": "Public RCSB acquisition only; downloaded structures remain unreviewed mutation-mapping candidates.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "downloaded_unique_structures": report["downloaded_unique_structures"],
            "already_present_unique_structures": report["already_present_unique_structures"],
            "failed_unique_structures": report["failed_unique_structures"],
            "candidate_rows_with_local_structure": report["candidate_rows_with_local_structure"],
            "output": str(args.report),
        },
        ensure_ascii=False,
    ))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
