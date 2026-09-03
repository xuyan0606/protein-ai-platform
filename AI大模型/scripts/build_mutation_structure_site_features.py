#!/usr/bin/env python3
"""Build local residue-neighborhood features for deterministically mapped mutations."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = AI_ROOT / "datasets" / "features" / "verified_mutation_structure_mapping_candidates.jsonl"
GRAPHS = AI_ROOT / "datasets" / "features" / "reviewed_structure_graph_features.jsonl"
OUT = AI_ROOT / "datasets" / "features" / "mutation_structure_site_features.jsonl"
REPORT = AI_ROOT / "reports" / "mutation_structure_site_feature_report.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else AI_ROOT / path


def pdb_neighborhood(path: Path, chain: str, author_number: int, cutoff: float) -> list[float]:
    target = None
    atoms: list[tuple[float, float, float, str]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.startswith("ATOM  ") or line[12:16].strip() != "CA":
                continue
            item_chain = line[21:22].strip() or "_"
            try:
                number = int(line[22:26].strip())
                point = (float(line[30:38]), float(line[38:46]), float(line[46:54]))
            except ValueError:
                continue
            if item_chain != chain:
                continue
            atoms.append((*point, str(number)))
            if number == author_number:
                target = point
    if target is None:
        return []
    distances = []
    for x, y, z, number in atoms:
        if int(number) == author_number:
            continue
        distance = math.sqrt(sum((left - right) ** 2 for left, right in zip(target, (x, y, z))))
        if distance <= cutoff:
            distances.append(round(distance, 3))
    return sorted(distances)


def build_feature(candidate: dict[str, Any], graph: dict[str, Any], pdb_distances: list[float] | None = None) -> dict[str, Any] | None:
    if candidate.get("mapping_status") != "deterministic_input_candidate":
        return None
    target = str(candidate.get("pdb_author_residue_number") or "")
    chain = str(candidate.get("selected_chain_id") or "")
    nodes = graph.get("nodes") or []
    node = next(
        (item for item in nodes if str(item.get("chain_id")) == chain and str(item.get("author_residue_number")) == target),
        None,
    )
    if node is None and not pdb_distances:
        return None
    node_id = node.get("node_id") if node else None
    distances = pdb_distances or [
        float(edge["distance_angstrom"])
        for edge in graph.get("edges") or []
        if edge.get("source") == node_id or edge.get("target") == node_id
    ]
    return {
        "feature_id": f"{candidate.get('candidate_id')}::site-graph-v1",
        "record_id": candidate.get("record_id"),
        "candidate_id": candidate.get("candidate_id"),
        "structure_id": candidate.get("executed_structure_id") or candidate.get("structure_id"),
        "selected_chain_id": chain,
        "pdb_author_residue_number": candidate.get("pdb_author_residue_number"),
        "wild_type": candidate.get("wild_type"),
        "mutant": candidate.get("mutant"),
        "structure_context_scope": candidate.get("structure_context_scope"),
        "neighbor_cutoff_angstrom": float(graph.get("neighbor_cutoff_angstrom") or 8.0),
        "neighbor_count": len(distances),
        "mean_neighbor_distance_angstrom": round(sum(distances) / len(distances), 3) if distances else None,
        "minimum_neighbor_distance_angstrom": round(min(distances), 3) if distances else None,
        "ligand_or_nonprotein_context_present": candidate.get("ligand_or_nonprotein_context_present") is True,
        "mapping_status": candidate.get("mapping_status"),
        "feature_scope": "deterministic_pdb_mutation_site" if pdb_distances is not None else "reviewed_graph_deterministic_mutation_site",
        "training_label": False,
        "safe_for_model_claim": False,
        "release_ready": False,
        "policy": "Local coordinate neighborhood only; not a label upgrade, physics result, or model-quality claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build mutation structure site features")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--graphs", type=Path, default=GRAPHS)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()

    graph_rows = load_jsonl(args.graphs)
    graph_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in graph_rows:
        path = resolve(str(row.get("graph_path") or ""))
        if path.exists():
            graph_by_key[(str(row.get("structure_id")), str(row.get("selected_chain_id")))] = json.loads(path.read_text(encoding="utf-8"))

    output: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for candidate in load_jsonl(args.candidates):
        if candidate.get("mapping_status") != "deterministic_input_candidate":
            skipped["mapping_not_deterministic"] += 1
            continue
        key = (str(candidate.get("executed_structure_id") or candidate.get("structure_id")), str(candidate.get("selected_chain_id")))
        graph = graph_by_key.get(key)
        distances = None
        if graph is None:
            structure_path = resolve(str(candidate.get("actual_cache_path") or ""))
            if structure_path.exists():
                distances = pdb_neighborhood(structure_path, str(candidate.get("selected_chain_id")), int(candidate.get("pdb_author_residue_number")), 8.0)
            if not distances:
                skipped["reviewed_graph_missing"] += 1
                continue
        feature = build_feature(candidate, graph or {}, distances)
        if feature is None:
            skipped["mapped_residue_not_in_graph"] += 1
            continue
        output.append(feature)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output), encoding="utf-8")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate_rows": len(load_jsonl(args.candidates)),
        "feature_rows": len(output),
        "feature_scope_counts": dict(Counter(row["feature_scope"] for row in output)),
        "skipped": dict(skipped),
        "safe_for_model_claim": False,
        "training_import_eligible_rows": 0,
        "policy": "Features require deterministic mutation mapping and reviewed graph; no training promotion is implied.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"feature_rows": len(output), "skipped": dict(skipped), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
