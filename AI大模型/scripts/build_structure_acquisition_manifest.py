#!/usr/bin/env python3
"""Prepare a local-only structure acquisition manifest without downloading."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
EXPECTED = AI_ROOT / "reports" / "structure_cache_expected_manifest.json"
OUT = AI_ROOT / "datasets" / "curation" / "structure_acquisition_manifest.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_acquisition_readiness_report.json"
CACHE_ROOT = AI_ROOT / "cache" / "structures"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def local_candidates(expected_path: str) -> list[Path]:
    path = CACHE_ROOT / expected_path
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local structure acquisition manifest")
    parser.add_argument("--expected", type=Path, default=EXPECTED)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    previous = {
        (str(row.get("source")), str(row.get("structure_id"))): row
        for row in load_jsonl(args.output)
    }
    CACHE_ROOT.joinpath("pdb").mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.joinpath("alphafold").mkdir(parents=True, exist_ok=True)
    rows = []
    for entry in expected.get("entries", []):
        source = entry.get("source")
        structure_id = str(entry.get("structure_id"))
        expected_path = entry.get("expected_path") or ""
        local_cache_path = CACHE_ROOT / expected_path
        actual_path = first_existing(local_candidates(expected_path))
        present = actual_path is not None
        row = {
            "structure_id": structure_id,
            "source": source,
            "expected_path": expected_path,
            "local_cache_path": str(local_cache_path),
            "actual_cache_path": str(actual_path) if actual_path else None,
            "actual_format": actual_path.suffix.lower().lstrip(".") if actual_path else None,
            "status": "present" if present else "missing",
            "retrieval_state": "already_present" if present else "not_started",
            "chain_mapping_required": bool(entry.get("chain_mapping_required", True)),
            "sha256": sha256_file(actual_path) if actual_path else None,
            "policy": "manifest only; no public download and no source DB modification",
        }
        if actual_path:
            row["local_validation"] = atom_chain_summary(actual_path)
        else:
            old = previous.get((str(source), structure_id), {})
            if old.get("retrieval_state") == "failed":
                row["retrieval_state"] = "failed"
                row["failure_reason"] = old.get("failure_reason")
                if old.get("retrieval_url"):
                    row["retrieval_url"] = old["retrieval_url"]
        rows.append({
            **row,
        })
    present_count = sum(1 for row in rows if row.get("status") == "present")
    report = {
        "entries": len(rows),
        "source_counts": dict(Counter(row.get("source") for row in rows)),
        "missing": len(rows) - present_count,
        "present": present_count,
        "coordinate_features_ready": present_count > 0,
        "cache_root": str(CACHE_ROOT),
        "manifest": str(args.output),
        "policy": "populate through an approved offline process, then audit and verify chain mapping",
    }
    write_jsonl(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "entries": report["entries"],
        "missing": report["missing"],
        "cache_root": report["cache_root"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
