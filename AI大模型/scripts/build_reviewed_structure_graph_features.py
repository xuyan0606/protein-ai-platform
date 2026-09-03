#!/usr/bin/env python3
"""Build reviewed structure residue-neighborhood graph cache.

The builder consumes only reviewed structure chain mappings. It creates local
coordinate graph artifacts and checksums, but it does not upgrade mutation-label
numbering or produce model-quality claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CURATED_MAPPINGS = AI_ROOT / "datasets" / "curation" / "structure_chain_mappings_curated.jsonl"
OUT = AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl"
MANIFEST_OUT = AI_ROOT / "reports" / "reviewed_structure_graph_manifest.json"
REPORT_OUT = AI_ROOT / "reports" / "reviewed_structure_graph_feature_report.json"
CACHE_ROOT = AI_ROOT / "cache" / "advanced_features" / "structure_graph"
NEIGHBOR_CUTOFF_A = 8.0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_structure_path(row: dict[str, Any]) -> tuple[Path | None, str | None]:
    """Resolve a reviewed cache path locally or under this project root by checksum."""
    configured_path = Path(str(row.get("actual_cache_path") or ""))
    expected_sha256 = str(row.get("sha256") or "")
    candidates = [configured_path]
    if configured_path.is_absolute() and "cache" in configured_path.parts:
        cache_index = configured_path.parts.index("cache")
        candidates.append(AI_ROOT.joinpath(*configured_path.parts[cache_index:]))

    for candidate in candidates:
        if not candidate.exists():
            continue
        if expected_sha256 and sha256(candidate) != expected_sha256:
            continue
        return candidate, None
    if expected_sha256:
        return None, "structure_file_missing_or_checksum_mismatch"
    return None, "structure_file_missing_without_checksum"


def parse_pdb_ca_atoms(path: Path, selected_chain: str) -> list[dict[str, Any]]:
    residues = []
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("ATOM  "):
                continue
            atom_name = line[12:16].strip()
            chain = line[21:22].strip() or "_"
            if atom_name != "CA" or chain != selected_chain:
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            residues.append({
                "node_id": len(residues),
                "chain_id": chain,
                "residue_name": line[17:20].strip(),
                "author_residue_number": line[22:26].strip(),
                "insertion_code": line[26:27].strip(),
                "x": x,
                "y": y,
                "z": z,
            })
    return residues


def parse_cif_ca_atoms(path: Path, selected_chain: str) -> list[dict[str, Any]]:
    residues = []
    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("ATOM"):
                continue
            parts = line.split()
            if len(parts) < 12:
                continue
            atom_name = parts[3]
            chain = parts[6] or "_"
            if atom_name != "CA" or chain != selected_chain:
                continue
            try:
                x = float(parts[10])
                y = float(parts[11])
                z = float(parts[12]) if len(parts) > 12 else 0.0
            except (ValueError, IndexError):
                continue
            residues.append({
                "node_id": len(residues),
                "chain_id": chain,
                "residue_name": parts[5],
                "author_residue_number": parts[8],
                "insertion_code": "",
                "x": x,
                "y": y,
                "z": z,
            })
    return residues


def parse_ca_atoms(path: Path, selected_chain: str) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".pdb":
        return parse_pdb_ca_atoms(path, selected_chain)
    if suffix == ".cif":
        return parse_cif_ca_atoms(path, selected_chain)
    return []


def distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)


def build_edges(nodes: list[dict[str, Any]], cutoff: float) -> list[dict[str, Any]]:
    edges = []
    for i, left in enumerate(nodes):
        for right in nodes[i + 1:]:
            dist = distance(left, right)
            if dist <= cutoff:
                edges.append({
                    "source": left["node_id"],
                    "target": right["node_id"],
                    "distance_angstrom": round(dist, 3),
                })
    return edges


def graph_payload(row: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]], input_sha256: str) -> dict[str, Any]:
    return {
        "graph_schema_version": "1.0.0",
        "structure_id": row.get("structure_id"),
        "uniprot_id": row.get("canonical_uniprot_id") or row.get("uniprot_id"),
        "selected_chain_id": row.get("selected_chain_id"),
        "sequence_to_structure_mapping_status": row.get("sequence_to_structure_mapping_status"),
        "residue_numbering_basis": row.get("residue_numbering_basis"),
        "input_structure_path": row.get("actual_cache_path"),
        "input_structure_sha256": input_sha256,
        "neighbor_cutoff_angstrom": NEIGHBOR_CUTOFF_A,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "local_only": True,
        "safe_for_model_claim": False,
        "requires_mutation_numbering_review": True,
        "policy": "Reviewed chain coordinate graph only; does not prove mutation label numbering or wet-lab effect.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build reviewed structure graph features")
    parser.add_argument("--curated-mappings", type=Path, default=CURATED_MAPPINGS)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--cache-root", type=Path, default=CACHE_ROOT)
    args = parser.parse_args()

    rows = load_jsonl(args.curated_mappings)
    args.cache_root.mkdir(parents=True, exist_ok=True)
    index_rows = []
    failures = []
    for row in rows:
        if not row.get("usable_for_coordinate_features"):
            continue
        structure_id = str(row.get("structure_id") or "").upper()
        selected_chain = str(row.get("selected_chain_id") or "")
        structure_path, resolution_error = resolve_structure_path(row)
        if not structure_id or not selected_chain:
            failures.append({"structure_id": structure_id, "reason": "missing_structure_id_or_chain"})
            continue
        if structure_path is None:
            failures.append({"structure_id": structure_id, "reason": resolution_error})
            continue
        nodes = parse_ca_atoms(structure_path, selected_chain)
        if not nodes:
            failures.append({"structure_id": structure_id, "reason": "selected_chain_ca_atoms_missing"})
            continue
        edges = build_edges(nodes, NEIGHBOR_CUTOFF_A)
        input_hash = sha256(structure_path)
        graph = graph_payload(row, nodes, edges, input_hash)
        graph_path = args.cache_root / f"{structure_id.lower()}_{selected_chain}.residue_graph.json"
        graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        graph_hash = sha256(graph_path)
        index_rows.append({
            "structure_id": structure_id,
            "uniprot_id": graph["uniprot_id"],
            "selected_chain_id": selected_chain,
            "graph_path": str(graph_path.relative_to(AI_ROOT)),
            "graph_sha256": graph_hash,
            "input_structure_sha256": input_hash,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "neighbor_cutoff_angstrom": NEIGHBOR_CUTOFF_A,
            "sequence_to_structure_mapping_status": graph["sequence_to_structure_mapping_status"],
            "residue_numbering_basis": graph["residue_numbering_basis"],
            "safe_for_structure_graph_feature_use": True,
            "safe_for_model_claim": False,
            "requires_mutation_numbering_review": True,
            "policy": "Use as reviewed chain coordinate graph only; not mutation numbering or wet-lab evidence.",
        })

    write_jsonl(args.output, index_rows)
    manifest = {
        "manifest_id": "kwb_reviewed_structure_graph_manifest",
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "cache_root": str(args.cache_root.relative_to(AI_ROOT) if args.cache_root.is_absolute() else args.cache_root),
        "index": str(args.output.relative_to(AI_ROOT) if args.output.is_absolute() else args.output),
        "graph_rows": len(index_rows),
        "failure_rows": len(failures),
        "status": "ready_for_coordinate_feature_use" if index_rows and not failures else "blocked_or_partial",
        "safe_for_model_claim": False,
        "policy": "Coordinate graph cache only. Mutation numbering, activity/stability labels and customer claims remain gated elsewhere.",
    }
    report = {
        "created_at": manifest["created_at"],
        "local_only": True,
        "curated_mapping_rows": len(rows),
        "graph_rows": len(index_rows),
        "failure_rows": len(failures),
        "node_count_total": sum(row["node_count"] for row in index_rows),
        "edge_count_total": sum(row["edge_count"] for row in index_rows),
        "mapping_status_counts": dict(Counter(row.get("sequence_to_structure_mapping_status") for row in index_rows)),
        "failures": failures[:200],
        "manifest": str(args.manifest.relative_to(AI_ROOT) if args.manifest.is_absolute() else args.manifest),
        "output": str(args.output.relative_to(AI_ROOT) if args.output.is_absolute() else args.output),
        "safe_for_model_claim": False,
        "policy": manifest["policy"],
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "graph_rows": report["graph_rows"],
        "failure_rows": report["failure_rows"],
        "safe_for_model_claim": report["safe_for_model_claim"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
