#!/usr/bin/env python3
"""Populate the local structure cache from public RCSB files.

This script writes only under AI大模型/cache/structures and updates the local
acquisition manifest/report. It does not modify the source database or promote
any model labels.
"""

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
INPUT = AI_ROOT / "datasets" / "curation" / "structure_acquisition_manifest.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_public_download_report.json"
RCSB_FILE_BASE = "https://files.rcsb.org/download"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_gzip(url: str, destination: Path, timeout: int) -> None:
    tmp_gz = destination.with_suffix(destination.suffix + ".download.gz")
    tmp_out = destination.with_suffix(destination.suffix + ".download")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            with tmp_gz.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        with gzip.open(tmp_gz, "rb") as src:
            with tmp_out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp_out.replace(destination)
    finally:
        if tmp_gz.exists():
            tmp_gz.unlink()
        if tmp_out.exists():
            tmp_out.unlink()


def local_candidates(path: Path) -> list[Path]:
    candidates = [path]
    if path.suffix.lower() == ".pdb":
        candidates.append(path.with_suffix(".cif"))
    elif path.suffix.lower() == ".cif":
        candidates.append(path.with_suffix(".pdb"))
    return candidates


def first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def atom_chain_summary(path: Path) -> dict[str, Any]:
    chains: dict[str, set[int]] = {}
    atom_lines = 0
    try:
        with path.open("rt", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.startswith(("ATOM  ", "HETATM")):
                    continue
                atom_lines += 1
                chain = (line[21:22].strip() or "_") if len(line) >= 22 else "_"
                raw_resseq = line[22:26].strip() if len(line) >= 26 else ""
                try:
                    resseq = int(raw_resseq)
                except ValueError:
                    continue
                chains.setdefault(chain, set()).add(resseq)
    except OSError:
        return {"atom_lines": 0, "chains": {}, "chain_mapping_required": True}
    return {
        "atom_lines": atom_lines,
        "chains": {chain: len(residues) for chain, residues in sorted(chains.items())},
        "chain_mapping_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Download public PDB files into the local structure cache")
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=INPUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--limit", type=int, default=0, help="Maximum missing structures to fetch; 0 means all")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format-order", default="pdb,cif", help="Comma-separated RCSB formats to try: pdb,cif")
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    attempted = 0
    downloaded = 0
    already_present = 0
    failed: list[dict[str, str]] = []
    touched: list[dict[str, Any]] = []
    format_order = [part.strip().lower() for part in args.format_order.split(",") if part.strip()]

    for row in rows:
        if row.get("source") != "pdb":
            continue
        local_path = Path(str(row.get("local_cache_path") or ""))
        actual_path = first_existing(local_candidates(local_path))
        if actual_path:
            row["status"] = "present"
            row["retrieval_state"] = "already_present"
            row["actual_cache_path"] = str(actual_path)
            row["actual_format"] = actual_path.suffix.lower().lstrip(".")
            row["sha256"] = sha256_file(actual_path)
            row["local_validation"] = atom_chain_summary(actual_path)
            already_present += 1
            continue
        if args.limit and attempted >= args.limit:
            continue
        attempted += 1
        pdb_id = str(row.get("structure_id") or "").upper()
        urls = []
        for fmt in format_order:
            if fmt not in {"pdb", "cif"}:
                continue
            target_path = local_path if fmt == local_path.suffix.lower().lstrip(".") else local_path.with_suffix(f".{fmt}")
            urls.append((fmt, f"{RCSB_FILE_BASE}/{pdb_id}.{fmt}.gz", target_path))
        row["retrieval_url"] = urls[0][1] if urls else None
        if args.dry_run:
            row["retrieval_state"] = "planned"
            touched.append({"structure_id": pdb_id, "urls": [url for _, url, _ in urls], "path": str(local_path)})
            continue
        errors = []
        try:
            for fmt, url, target_path in urls:
                try:
                    download_gzip(url, target_path, args.timeout)
                    row["status"] = "present"
                    row["retrieval_state"] = "fetched_public_rcsb"
                    row["retrieval_url"] = url
                    row["actual_cache_path"] = str(target_path)
                    row["actual_format"] = fmt
                    row["sha256"] = sha256_file(target_path)
                    row["local_validation"] = atom_chain_summary(target_path)
                    downloaded += 1
                    touched.append({
                        "structure_id": pdb_id,
                        "path": str(target_path),
                        "format": fmt,
                        "sha256": row["sha256"],
                        "atom_lines": row["local_validation"]["atom_lines"],
                        "chains": row["local_validation"]["chains"],
                    })
                    break
                except urllib.error.HTTPError as exc:
                    errors.append(f"{fmt}: HTTP {exc.code}")
                except Exception as exc:
                    errors.append(f"{fmt}: {exc}")
            else:
                raise RuntimeError("; ".join(errors) or "no usable download format")
        except urllib.error.HTTPError as exc:
            row["retrieval_state"] = "failed"
            row["status"] = "missing"
            row["failure_reason"] = f"HTTP {exc.code}"
            failed.append({"structure_id": pdb_id, "reason": row["failure_reason"]})
        except Exception as exc:
            row["retrieval_state"] = "failed"
            row["status"] = "missing"
            row["failure_reason"] = str(exc)
            failed.append({"structure_id": pdb_id, "reason": row["failure_reason"]})
        if args.sleep:
            time.sleep(args.sleep)

    present = sum(1 for row in rows if row.get("status") == "present")
    missing = sum(1 for row in rows if row.get("status") != "present")
    if not args.dry_run:
        write_jsonl(args.output, rows)
    report = {
        "local_only": True,
        "input": str(args.input),
        "output": str(args.output),
        "dry_run": args.dry_run,
        "attempted": attempted,
        "downloaded": downloaded,
        "already_present": already_present,
        "failed": len(failed),
        "present_after": present,
        "missing_after": missing,
        "failures": failed[:200],
        "touched": touched[:200],
        "policy": "public RCSB acquisition only; chain mapping still requires validation before coordinate-level model claims",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "attempted": attempted,
        "downloaded": downloaded,
        "failed": len(failed),
        "present_after": present,
        "missing_after": missing,
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
