#!/usr/bin/env python3
"""Build public-PDB acquisition candidates for verified mutation records.

The selector consumes locally cached UniProt records. It does not download
structures, change labels, or turn a source-database cross-reference into a
reviewed structure/mutation mapping.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
VERIFIED_ROWS = AI_ROOT / "datasets" / "curated" / "enzyme_mutation_training_table_verified.jsonl"
UNIPROT_CACHE = AI_ROOT / "datasets" / "curation" / "numbering_public_evidence" / "uniprot_entries"
OUT = AI_ROOT / "datasets" / "curation" / "verified_mutation_structure_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "verified_mutation_structure_candidate_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def properties(reference: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("key")): str(item.get("value"))
        for item in reference.get("properties") or []
        if isinstance(item, dict) and item.get("key") is not None
    }


def parse_resolution(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    return float(match.group(1)) if match else None


def is_xray(value: str | None) -> bool:
    return "x-ray" in str(value or "").lower() or "xray" in str(value or "").lower()


def rank_reference(reference: dict[str, Any]) -> tuple[int, float, str]:
    props = properties(reference)
    resolution = parse_resolution(props.get("Resolution"))
    return (
        0 if is_xray(props.get("Method")) else 1,
        resolution if resolution is not None else 9999.0,
        str(reference.get("id") or ""),
    )


def pdb_references(entry: dict[str, Any]) -> list[dict[str, Any]]:
    refs = [
        reference
        for reference in entry.get("uniProtKBCrossReferences") or []
        if isinstance(reference, dict) and reference.get("database") == "PDB" and reference.get("id")
    ]
    return sorted(refs, key=rank_reference)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build verified-mutation public PDB candidates")
    parser.add_argument("--verified-rows", type=Path, default=VERIFIED_ROWS)
    parser.add_argument("--uniprot-cache", type=Path, default=UNIPROT_CACHE)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.verified_rows)
    previous = {
        str(row.get("candidate_id")): row
        for row in load_jsonl(args.output)
        if row.get("candidate_id")
    }
    candidates: list[dict[str, Any]] = []
    missing_cache: list[str] = []
    without_pdb: list[str] = []
    for row in rows:
        accession = str(row.get("uniprot_id") or "")
        cache_path = args.uniprot_cache / f"{accession}.json"
        if not accession or not cache_path.exists():
            missing_cache.append(accession or str(row.get("record_id") or "unknown"))
            continue
        try:
            entry = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            missing_cache.append(accession)
            continue
        references = pdb_references(entry)
        if not references:
            without_pdb.append(accession)
            continue
        selected = references[0]
        props = properties(selected)
        structure_id = str(selected["id"]).upper()
        candidate = {
                "candidate_id": f"{row.get('record_id')}::PDB:{structure_id}",
                "record_id": row.get("record_id"),
                "uniprot_id": accession,
                "mutation": row.get("mutation"),
                "mutation_position": row.get("mutation_position"),
                "wild_type": row.get("wild_type"),
                "mutant": row.get("mutant"),
                "numbering_verified_by_sequence": row.get("numbering_verified_by_sequence") is True,
                "source_label_status": row.get("curation_status"),
                "structure_id": structure_id,
                "structure_source": "UniProt PDB cross-reference",
                "structure_method": props.get("Method"),
                "structure_resolution_angstrom": parse_resolution(props.get("Resolution")),
                "uniprot_chain_ranges": props.get("Chains"),
                "selection_policy": "prefer X-ray; then lowest reported resolution; then lexical PDB id",
                "fallback_structure_ids": [str(reference["id"]).upper() for reference in references[1:]],
                "source_uniprot_cache": str(cache_path.relative_to(AI_ROOT)),
                "download_url": f"https://files.rcsb.org/download/{structure_id}.pdb.gz",
                "expected_cache_path": f"cache/structures/verified_mutations/pdb/{structure_id.lower()}.pdb",
                "acquisition_status": "candidate_not_downloaded",
                "mapping_status": "not_mapped",
                "pose_position": None,
                "usable_as_physics_input_feature": False,
                "training_label": False,
                "safe_for_model_claim": False,
                "release_ready": False,
                "policy": (
                    "Public PDB candidate only. Download and strict chain/author-numbering/WT checks "
                    "are required before any computational feature can be used."
                ),
            }
        old = previous.get(str(candidate["candidate_id"]), {})
        for key in ("actual_cache_path", "structure_sha256", "acquisition_status", "download_error"):
            if key in old:
                candidate[key] = old[key]
        candidates.append(candidate)

    candidates.sort(key=lambda item: (str(item.get("uniprot_id")), str(item.get("record_id"))))
    write_jsonl(args.output, candidates)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verified_mutation_rows": len(rows),
        "candidate_rows": len(candidates),
        "unique_structures": len({row["structure_id"] for row in candidates}),
        "missing_uniprot_cache_rows": len(missing_cache),
        "without_pdb_cross_reference_rows": len(without_pdb),
        "method_counts": dict(Counter(row.get("structure_method") or "unknown" for row in candidates)),
        "output": str(args.output.relative_to(AI_ROOT)),
        "safe_for_model_claim": False,
        "policy": "Candidate selection from local UniProt evidence only; not a reviewed mapping or training-label import.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "verified_mutation_rows": report["verified_mutation_rows"],
            "candidate_rows": report["candidate_rows"],
            "unique_structures": report["unique_structures"],
            "output": str(args.report),
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
