#!/usr/bin/env python3
"""Build local structure coordinate summary features.

The output is a coordinate-readiness feature table. It does not establish
sequence-to-structure residue mapping and must not be used for model-quality
claims until chain/numbering curation is complete.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = AI_ROOT / "datasets" / "curation" / "structure_acquisition_manifest.jsonl"
OUT = AI_ROOT / "datasets" / "curation" / "structure_coordinate_features.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "structure_coordinate_feature_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def parse_pdb(path: Path) -> dict[str, Any]:
    atom_lines = 0
    hetatm_lines = 0
    ca_atoms = 0
    residues_by_chain: dict[str, set[str]] = defaultdict(set)
    atom_counts_by_chain: Counter[str] = Counter()
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            is_het = line.startswith("HETATM")
            atom_lines += 0 if is_het else 1
            hetatm_lines += 1 if is_het else 0
            atom_name = line[12:16].strip()
            chain = line[21:22].strip() or "_"
            residue_key = f"{line[22:26].strip()}:{line[26:27].strip()}"
            atom_counts_by_chain[chain] += 1
            residues_by_chain[chain].add(residue_key)
            if atom_name == "CA" and not is_het:
                ca_atoms += 1
    return {
        "atom_lines": atom_lines,
        "hetatm_lines": hetatm_lines,
        "ca_atoms": ca_atoms,
        "chain_count": len(residues_by_chain),
        "residue_count_total": sum(len(items) for items in residues_by_chain.values()),
        "residue_count_by_chain": {chain: len(items) for chain, items in sorted(residues_by_chain.items())},
        "atom_count_by_chain": dict(sorted(atom_counts_by_chain.items())),
    }


def parse_cif(path: Path) -> dict[str, Any]:
    atom_lines = 0
    hetatm_lines = 0
    ca_atoms = 0
    residues_by_chain: dict[str, set[str]] = defaultdict(set)
    atom_counts_by_chain: Counter[str] = Counter()
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith(("ATOM", "HETATM")):
                continue
            parts = line.split()
            if len(parts) < 9:
                continue
            is_het = parts[0] == "HETATM"
            atom_lines += 0 if is_het else 1
            hetatm_lines += 1 if is_het else 0
            atom_name = parts[3]
            chain = parts[6] or "_"
            seq_id = parts[8]
            atom_counts_by_chain[chain] += 1
            residues_by_chain[chain].add(seq_id)
            if atom_name == "CA" and not is_het:
                ca_atoms += 1
    return {
        "atom_lines": atom_lines,
        "hetatm_lines": hetatm_lines,
        "ca_atoms": ca_atoms,
        "chain_count": len(residues_by_chain),
        "residue_count_total": sum(len(items) for items in residues_by_chain.values()),
        "residue_count_by_chain": {chain: len(items) for chain, items in sorted(residues_by_chain.items())},
        "atom_count_by_chain": dict(sorted(atom_counts_by_chain.items())),
    }


def parse_structure(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".pdb":
        return parse_pdb(path)
    if suffix == ".cif":
        return parse_cif(path)
    return {
        "atom_lines": 0,
        "hetatm_lines": 0,
        "ca_atoms": 0,
        "chain_count": 0,
        "residue_count_total": 0,
        "residue_count_by_chain": {},
        "atom_count_by_chain": {},
        "parse_warning": f"unsupported_format:{suffix}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build structure coordinate summary features")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    args = parser.parse_args()

    manifest_rows = load_jsonl(args.manifest)
    output_rows = []
    parse_failures = []
    for row in manifest_rows:
        if row.get("status") != "present":
            continue
        path_text = row.get("actual_cache_path") or row.get("local_cache_path")
        path = Path(str(path_text))
        if not path.exists():
            parse_failures.append({"structure_id": row.get("structure_id"), "reason": "missing_actual_file"})
            continue
        try:
            parsed = parse_structure(path)
        except Exception as exc:
            parse_failures.append({"structure_id": row.get("structure_id"), "reason": str(exc)})
            continue
        output_rows.append({
            "structure_id": row.get("structure_id"),
            "source": row.get("source"),
            "expected_path": row.get("expected_path"),
            "actual_cache_path": str(path),
            "actual_format": row.get("actual_format") or path.suffix.lower().lstrip("."),
            "sha256": row.get("sha256"),
            **parsed,
            "coordinate_feature_scope": "file_level_chain_residue_summary",
            "requires_chain_numbering_review": True,
            "policy": "coordinate summary only; no sequence-to-structure mapping decision",
        })

    write_jsonl(args.output, output_rows)
    format_counts = Counter(row.get("actual_format") for row in output_rows)
    report = {
        "manifest_rows": len(manifest_rows),
        "feature_rows": len(output_rows),
        "parse_failures": len(parse_failures),
        "format_counts": dict(format_counts),
        "structures_with_atoms": sum(1 for row in output_rows if row.get("atom_lines", 0) > 0),
        "structures_with_ca_atoms": sum(1 for row in output_rows if row.get("ca_atoms", 0) > 0),
        "chain_count_distribution": dict(Counter(str(row.get("chain_count")) for row in output_rows)),
        "failures": parse_failures[:200],
        "output": str(args.output),
        "policy": "chain mapping is not reviewed; use as P27 input only",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "feature_rows": report["feature_rows"],
        "parse_failures": report["parse_failures"],
        "format_counts": report["format_counts"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not parse_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
