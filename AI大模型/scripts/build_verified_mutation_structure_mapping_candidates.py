#!/usr/bin/env python3
"""Map verified mutation positions onto downloaded PDB chains.

This builder creates deterministic, input-only mapping candidates. It does not
write reviewed decisions, training rows, ddG labels, or model claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from array import array
from collections import Counter
from pathlib import Path
from typing import Any

from ddg_python_module_discovery import add_local_module_paths


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "curation" / "verified_mutation_structure_candidates.jsonl"
UNIPROT_CACHE = AI_ROOT / "datasets" / "curation" / "numbering_public_evidence" / "uniprot_entries"
OUT = AI_ROOT / "datasets" / "features" / "verified_mutation_structure_mapping_candidates.jsonl"
REPORT = AI_ROOT / "reports" / "verified_mutation_structure_mapping_candidate_report.json"

AA3 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "MSE": "M",
}


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_pdb_chains(path: Path) -> dict[str, list[dict[str, Any]]]:
    chains: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str, str]] = set()
    in_first_model = True
    saw_model = False
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("MODEL"):
                if saw_model:
                    in_first_model = False
                else:
                    saw_model = True
                continue
            if line.startswith("ENDMDL") and saw_model:
                in_first_model = False
                continue
            if not in_first_model or not line.startswith("ATOM  "):
                continue
            if line[12:16].strip() != "CA":
                continue
            altloc = line[16:17].strip()
            if altloc not in {"", "A"}:
                continue
            chain = line[21:22].strip() or "_"
            author_number = line[22:26].strip()
            insertion_code = line[26:27].strip()
            key = (chain, author_number, insertion_code)
            if key in seen:
                continue
            residue_name = line[17:20].strip().upper()
            one_letter = AA3.get(residue_name)
            if one_letter is None:
                continue
            try:
                author_position = int(author_number)
            except ValueError:
                continue
            seen.add(key)
            chains.setdefault(chain, []).append(
                {
                    "chain_id": chain,
                    "author_residue_number": author_number,
                    "author_position": author_position,
                    "insertion_code": insertion_code,
                    "residue_name": residue_name,
                    "one_letter": one_letter,
                }
            )
    return chains


def parse_hetero_residue_names(path: Path) -> list[str]:
    """List non-water HETATM residue names without claiming ligand parameterization."""
    names: set[str] = set()
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("HETATM"):
                continue
            residue_name = line[17:20].strip().upper()
            if residue_name and residue_name not in {"HOH", "WAT", "DOD"}:
                names.add(residue_name)
    return sorted(names)


def executed_structure_id(path: Path) -> str:
    return path.stem.upper()


def coverage_scope(observed_coverage: float | None) -> str:
    if observed_coverage is None:
        return "unknown"
    if observed_coverage >= 0.8:
        return "near_full_length_context"
    return "partial_domain_context"


def global_alignment(canonical: str, observed: str) -> tuple[dict[int, int | None], float]:
    """Return 1-based canonical-position -> 0-based observed-index mapping."""
    gap = -2
    match = 2
    mismatch = -1
    previous = array("h", [j * gap for j in range(len(observed) + 1)])
    traces: list[bytearray] = []
    for i, canonical_char in enumerate(canonical, start=1):
        current = array("h", [i * gap])
        trace = bytearray(len(observed) + 1)
        for j, observed_char in enumerate(observed, start=1):
            diagonal = previous[j - 1] + (match if canonical_char == observed_char else mismatch)
            up = previous[j] + gap
            left = current[j - 1] + gap
            best = max(diagonal, up, left)
            current.append(best)
            if best == diagonal:
                trace[j] = 0
            elif best == up:
                trace[j] = 1
            else:
                trace[j] = 2
        traces.append(trace)
        previous = current

    mapping: dict[int, int | None] = {}
    i = len(canonical)
    j = len(observed)
    matches = 0
    aligned = 0
    while i > 0 or j > 0:
        direction = traces[i - 1][j] if i > 0 and j >= 0 else 2
        if i > 0 and j > 0 and direction == 0:
            i -= 1
            j -= 1
            mapping[i + 1] = j
            aligned += 1
            if canonical[i] == observed[j]:
                matches += 1
        elif i > 0 and (j == 0 or direction == 1):
            i -= 1
            mapping[i + 1] = None
        else:
            j -= 1
    identity = matches / aligned if aligned else 0.0
    return mapping, identity


def parse_chain_ranges(value: str | None) -> dict[str, list[tuple[int, int]]]:
    result: dict[str, list[tuple[int, int]]] = {}
    for match in re.finditer(r"([A-Za-z0-9/_]+)\s*=\s*(\d+)\s*-\s*(\d+)", str(value or "")):
        chain_names, start, end = match.groups()
        for chain in chain_names.split("/"):
            result.setdefault(chain, []).append((int(start), int(end)))
    return result


def chain_is_in_range(chain: str, position: int, ranges: dict[str, list[tuple[int, int]]]) -> bool:
    if not ranges:
        return True
    if chain not in ranges:
        return False
    return any(start <= position <= end for start, end in ranges[chain])


def load_canonical_sequence(accession: str, cache: Path) -> str:
    path = cache / f"{accession}.json"
    if not path.exists():
        return ""
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    return str((entry.get("sequence") or {}).get("value") or "").replace("\n", "").strip().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic mutation-to-PDB mapping candidates")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--uniprot-cache", type=Path, default=UNIPROT_CACHE)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    rows = load_jsonl(args.candidates)
    try:
        add_local_module_paths()
        import pyrosetta  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"PyRosetta import failed: {type(exc).__name__}: {exc}") from exc
    # Mapping only: unrecognized ligands are irrelevant to pdb2pose and must
    # not make an otherwise usable protein chain abort the entire batch.
    pyrosetta.init("-mute all -ignore_unrecognized_res true")

    output: list[dict[str, Any]] = []
    pose_cache: dict[str, Any] = {}
    pose_errors: dict[str, str] = {}
    for row in rows:
        path_text = str(row.get("actual_cache_path") or "").strip()
        structure_path = Path(path_text) if path_text else None
        if structure_path is not None and not structure_path.is_absolute():
            structure_path = AI_ROOT / structure_path
        source_structure_id = str(row.get("structure_id") or "").upper() or None
        actual_structure_id = (
            executed_structure_id(structure_path)
            if structure_path is not None and structure_path.is_file()
            else None
        )
        base = {
            **row,
            "source_structure_id": source_structure_id,
            "executed_structure_id": actual_structure_id,
            "source_executed_structure_match": (
                source_structure_id == actual_structure_id
                if source_structure_id and actual_structure_id
                else None
            ),
            "structure_sha256_observed": (
                sha256(structure_path) if structure_path is not None and structure_path.is_file() else None
            ),
            "mapping_status": "blocked",
            "mapping_blockers": [],
            "canonical_sequence_length": None,
            "selected_chain_id": None,
            "alignment_identity": None,
            "alignment_observed_coverage": None,
            "pdb_author_residue_number": None,
            "pdb_insertion_code": None,
            "pdb_observed_residue_one_letter": None,
            "residue_present": False,
            "wt_residue_match": False,
            "pose_position": None,
            "pose_mapping_method": "PyRosetta pose.pdb_info().pdb2pose",
            "structure_context_scope": "unknown",
            "hetero_residue_names_observed": [],
            "ligand_or_nonprotein_context_present": False,
            "ligand_handling_policy": "ignore_unrecognized_res_true",
            "ligand_modeling_complete": False,
            "usable_as_physics_input_feature": False,
            "training_label": False,
            "safe_for_model_claim": False,
            "release_ready": False,
        }
        if structure_path is None or not structure_path.is_file():
            base["mapping_blockers"].append("structure_file_missing")
            output.append(base)
            continue
        accession = str(row.get("uniprot_id") or "")
        canonical = load_canonical_sequence(accession, args.uniprot_cache)
        base["canonical_sequence_length"] = len(canonical)
        if not canonical:
            base["mapping_blockers"].append("canonical_uniprot_sequence_missing")
            output.append(base)
            continue
        chains = parse_pdb_chains(structure_path)
        hetero_residue_names = parse_hetero_residue_names(structure_path)
        base["hetero_residue_names_observed"] = hetero_residue_names
        base["ligand_or_nonprotein_context_present"] = bool(hetero_residue_names)
        if not chains:
            base["mapping_blockers"].append("no_ca_chain_residues")
            output.append(base)
            continue
        chain_ranges = parse_chain_ranges(row.get("uniprot_chain_ranges"))
        position = int(row.get("mutation_position") or 0)
        chain_candidates: list[dict[str, Any]] = []
        pose_load_failed = False
        for chain_id, residues in chains.items():
            if not chain_is_in_range(chain_id, position, chain_ranges):
                continue
            observed = "".join(residue["one_letter"] for residue in residues)
            mapping, identity = global_alignment(canonical, observed)
            observed_index = mapping.get(position)
            if observed_index is None:
                continue
            residue = residues[observed_index]
            pose = pose_cache.get(str(structure_path))
            if pose is None and str(structure_path) not in pose_errors:
                try:
                    pose = pyrosetta.pose_from_pdb(str(structure_path))
                    pose_cache[str(structure_path)] = pose
                except Exception as exc:
                    pose_errors[str(structure_path)] = f"{type(exc).__name__}: {exc}"
            if pose is None:
                base["mapping_blockers"].append(
                    "pyrosetta_pose_load_failed:" + pose_errors.get(str(structure_path), "unknown")
                )
                pose_load_failed = True
                break
            pdb_info = pose.pdb_info()
            try:
                pose_position = int(
                    pdb_info.pdb2pose(
                        chain_id,
                        int(residue["author_position"]),
                        str(residue["insertion_code"] or " "),
                    )
                )
            except TypeError:
                pose_position = int(pdb_info.pdb2pose(chain_id, int(residue["author_position"])))
            except Exception:
                pose_position = 0
            chain_candidates.append(
                {
                    "chain_id": chain_id,
                    "residue": residue,
                    "alignment_identity": round(identity, 6),
                    "observed_coverage": round(len(observed) / len(canonical), 6) if canonical else 0.0,
                    "chain_ca_residue_count": len(residues),
                    "author_residue_min": min(item["author_position"] for item in residues),
                    "author_residue_max": max(item["author_position"] for item in residues),
                    "pose_position": pose_position,
                }
            )
        if pose_load_failed:
            output.append(base)
            continue
        if not chain_candidates:
            base["mapping_blockers"].append("target_position_not_mapped_by_canonical_to_pdb_alignment")
            output.append(base)
            continue
        base["chain_mapping_candidates"] = [
            {
                "chain_id": item["chain_id"],
                "author_residue_number": item["residue"]["author_position"],
                "insertion_code": item["residue"]["insertion_code"],
                "observed_residue_one_letter": item["residue"]["one_letter"],
                "alignment_identity": item["alignment_identity"],
                "observed_coverage": item["observed_coverage"],
                "chain_ca_residue_count": item["chain_ca_residue_count"],
                "author_residue_min": item["author_residue_min"],
                "author_residue_max": item["author_residue_max"],
                "pose_position": item["pose_position"],
                "wt_match": item["residue"]["one_letter"] == str(row.get("wild_type") or ""),
            }
            for item in chain_candidates
        ]
        matching = [
            candidate
            for candidate in chain_candidates
            if candidate["residue"]["one_letter"] == str(row.get("wild_type") or "")
            and candidate["pose_position"] > 0
        ]
        chosen = matching[0] if len(matching) == 1 else None
        if len(matching) > 1:
            base["mapping_status"] = "blocked_ambiguous_multiple_chains"
            base["mapping_blockers"].append("multiple_chains_match_wild_type_and_pose")
        elif not matching:
            base["mapping_status"] = "blocked_wild_type_or_pose_mismatch"
            base["mapping_blockers"].append("no_unique_chain_with_expected_wild_type_and_pose")
        else:
            residue = chosen["residue"]
            base.update(
                {
                    "mapping_status": "deterministic_input_candidate",
                    "selected_chain_id": chosen["chain_id"],
                    "alignment_identity": chosen["alignment_identity"],
                    "alignment_observed_coverage": chosen["observed_coverage"],
                    "structure_context_scope": coverage_scope(chosen["observed_coverage"]),
                    "pdb_author_residue_number": residue["author_position"],
                    "pdb_insertion_code": residue["insertion_code"],
                    "pdb_observed_residue_one_letter": residue["one_letter"],
                    "residue_present": True,
                    "wt_residue_match": True,
                    "pose_position": chosen["pose_position"],
                    "usable_as_physics_input_feature": True,
                    "mapping_blockers": [],
                }
            )
        base["candidate_chain_count"] = len(chain_candidates)
        base["matching_chain_count"] = len(matching)
        if base["structure_context_scope"] == "unknown" and matching:
            base["structure_context_scope"] = coverage_scope(
                max(float(item["observed_coverage"]) for item in matching)
            )
        output.append(base)

    write_jsonl(args.output, output)
    status_counts = Counter(str(row.get("mapping_status")) for row in output)
    report = {
        "input_rows": len(rows),
        "output_rows": len(output),
        "mapping_status_counts": dict(status_counts),
        "deterministic_input_candidate_rows": sum(
            1 for row in output if row.get("mapping_status") == "deterministic_input_candidate"
        ),
        "pose_position_rows": sum(1 for row in output if int(row.get("pose_position") or 0) > 0),
        "structure_hash_mismatch_rows": sum(
            1
            for row in output
            if row.get("structure_sha256")
            and row.get("structure_sha256_observed")
            and row.get("structure_sha256") != row.get("structure_sha256_observed")
        ),
        "source_executed_structure_mismatch_rows": sum(
            1 for row in output if row.get("source_executed_structure_match") is False
        ),
        "partial_domain_context_rows": sum(
            1 for row in output if row.get("structure_context_scope") == "partial_domain_context"
        ),
        "ligand_or_nonprotein_context_rows": sum(
            1 for row in output if row.get("ligand_or_nonprotein_context_present") is True
        ),
        "pyrosetta_init_executed": True,
        "output": str(args.output.relative_to(AI_ROOT)),
        "safe_for_model_claim": False,
        "policy": (
            "Deterministic input candidate only. It is not a human reviewed numbering decision, "
            "not a wet-lab label, and not training-import or model-claim eligible."
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "input_rows": report["input_rows"],
            "deterministic_input_candidate_rows": report["deterministic_input_candidate_rows"],
            "pose_position_rows": report["pose_position_rows"],
            "mapping_status_counts": report["mapping_status_counts"],
            "output": str(args.report),
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
