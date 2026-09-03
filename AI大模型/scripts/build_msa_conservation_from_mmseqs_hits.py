#!/usr/bin/env python3
"""Build per-target MSA/conservation cache from real MMseqs2 Swiss-Prot hits."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_ROOT = Path(__file__).resolve().parents[1]
CONFIG = AI_ROOT / "config" / "msa_runtime.local.example.json"
TARGETS_FASTA = AI_ROOT / "datasets" / "curation" / "msa_inputs" / "msa_targets.fasta"
TARGETS_JSONL = AI_ROOT / "datasets" / "curation" / "msa_conservation_targets.jsonl"
HITS = AI_ROOT / "cache" / "msa" / "mmseqs_swissprot_hits.m8"
MSA_ROOT = AI_ROOT / "cache" / "msa"
CONSERVATION_ROOT = AI_ROOT / "datasets" / "curation" / "msa_conservation"
INTAKE_OUT = AI_ROOT / "datasets" / "curation" / "msa_trusted_cache_intake.local.jsonl"
REPORT_OUT = AI_ROOT / "reports" / "msa_mmseqs_swissprot_cache_build_report.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_fasta(path: Path) -> dict[str, str]:
    records: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            current = line[1:].split()[0]
            records[current] = []
        elif current:
            records[current].append(line.strip())
    return {key: "".join(value) for key, value in records.items()}


def wrap(text: str, width: int = 80) -> str:
    return "\n".join(text[index:index + width] for index in range(0, len(text), width))


def resolve_project_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else AI_ROOT / path


def run_search(config: dict[str, Any], hits: Path, threads: int, max_seqs: int) -> dict[str, Any]:
    mmseqs = resolve_project_path(((config.get("local_binary") or {}).get("binary_path")))
    db = resolve_project_path(((config.get("homolog_database") or {}).get("database_path")))
    if not mmseqs or not mmseqs.exists() or not db or not db.exists():
        return {"returncode": 127, "stdout": "", "stderr": "mmseqs_binary_or_database_missing"}
    tmp = AI_ROOT / "cache" / "msa" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    command = [
        str(mmseqs),
        "easy-search",
        str(TARGETS_FASTA),
        str(db),
        str(hits),
        str(tmp),
        "--threads",
        str(threads),
        "--max-seqs",
        str(max_seqs),
        "-a",
        "1",
        "--format-output",
        "query,target,pident,qstart,qend,qlen,tstart,tend,tlen,alnlen,evalue,bits,qaln,taln",
    ]
    proc = subprocess.run(
        command,
        cwd=AI_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def load_hits(path: Path) -> dict[str, list[dict[str, Any]]]:
    hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.exists():
        return hits
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 14:
            continue
        query, target = parts[0], parts[1]
        try:
            row = {
                "query": query,
                "target": target,
                "pident": float(parts[2]),
                "qstart": int(parts[3]),
                "qend": int(parts[4]),
                "qlen": int(parts[5]),
                "tstart": int(parts[6]),
                "tend": int(parts[7]),
                "tlen": int(parts[8]),
                "alnlen": int(parts[9]),
                "evalue": parts[10],
                "bits": float(parts[11]),
                "qaln": parts[12],
                "taln": parts[13],
            }
        except ValueError:
            continue
        hits[query].append(row)
    for query_hits in hits.values():
        query_hits.sort(key=lambda item: (-item["bits"], float(item["evalue"].replace("E", "e"))))
    return hits


def aligned_target_to_query(hit: dict[str, Any], query_sequence: str) -> tuple[str, list[int], list[int]]:
    aligned = ["-"] * len(query_sequence)
    covered = [0] * len(query_sequence)
    matched = [0] * len(query_sequence)
    qpos = int(hit["qstart"]) - 1
    qaln = hit["qaln"]
    taln = hit["taln"]
    for q_char, t_char in zip(qaln, taln):
        if q_char == "-":
            continue
        if 0 <= qpos < len(query_sequence):
            if t_char != "-":
                aligned[qpos] = t_char
                covered[qpos] = 1
                if t_char == query_sequence[qpos]:
                    matched[qpos] = 1
        qpos += 1
    return "".join(aligned), covered, matched


def build_cache_for_target(
    uniprot_id: str,
    sequence: str,
    hits: list[dict[str, Any]],
    max_hits: int,
    msa_root: Path,
    conservation_root: Path,
    source_database: str,
    database_version: str,
) -> dict[str, Any]:
    selected = hits[:max_hits]
    depth = [0] * len(sequence)
    matches = [0] * len(sequence)
    msa_lines = [f">{uniprot_id}|query", wrap(sequence)]
    for hit in selected:
        aligned, covered, matched = aligned_target_to_query(hit, sequence)
        depth = [a + b for a, b in zip(depth, covered)]
        matches = [a + b for a, b in zip(matches, matched)]
        header = f">{hit['target']}|pident={hit['pident']:.3f}|evalue={hit['evalue']}|bits={hit['bits']:.1f}"
        msa_lines.extend([header, wrap(aligned)])
    conservation = [round(matches[index] / depth[index], 6) if depth[index] else 0.0 for index in range(len(sequence))]
    covered_positions = sum(1 for value in depth if value > 0)
    mean_depth = sum(depth) / len(depth) if depth else 0.0

    msa_path = msa_root / f"{uniprot_id}.aln.fasta"
    conservation_path = conservation_root / f"{uniprot_id}.conservation.json"
    msa_path.parent.mkdir(parents=True, exist_ok=True)
    conservation_path.parent.mkdir(parents=True, exist_ok=True)
    msa_path.write_text("\n".join(msa_lines) + "\n", encoding="utf-8")
    payload = {
        "uniprot_id": uniprot_id,
        "sequence_length": len(sequence),
        "source": "mmseqs2_swissprot_pairwise_alignment_stack",
        "source_database": source_database,
        "database_version": database_version,
        "hit_count": len(selected),
        "raw_hit_count": len(hits),
        "position_conservation": conservation,
        "summary": {
            "positions_with_homolog_coverage": covered_positions,
            "mean_homolog_depth": round(mean_depth, 6),
            "max_homolog_depth": max(depth) if depth else 0,
            "method": "Fraction of selected Swiss-Prot pairwise alignments matching the query residue at each position.",
        },
        "policy": "Real MMseqs2 Swiss-Prot alignments; not single-sequence pseudo-conservation.",
    }
    conservation_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "uniprot_id": uniprot_id,
        "sequence_length": len(sequence),
        "source": payload["source"],
        "source_database": source_database,
        "database_version": database_version,
        "msa_path": str(msa_path.relative_to(AI_ROOT)),
        "msa_sha256": sha256(msa_path),
        "conservation_feature_path": str(conservation_path.relative_to(AI_ROOT)),
        "conservation_sha256": sha256(conservation_path),
        "reviewer": "local_mmseqs2_pipeline",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "notes": f"raw_hit_count={len(hits)}; selected_hit_count={len(selected)}; mean_depth={mean_depth:.6f}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MSA/conservation cache from MMseqs Swiss-Prot hits")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--targets-fasta", type=Path, default=TARGETS_FASTA)
    parser.add_argument("--targets-jsonl", type=Path, default=TARGETS_JSONL)
    parser.add_argument("--hits", type=Path, default=HITS)
    parser.add_argument("--msa-root", type=Path, default=MSA_ROOT)
    parser.add_argument("--conservation-root", type=Path, default=CONSERVATION_ROOT)
    parser.add_argument("--intake-output", type=Path, default=INTAKE_OUT)
    parser.add_argument("--report", type=Path, default=REPORT_OUT)
    parser.add_argument("--max-hits-per-target", type=int, default=128)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()

    config = load_json(args.config)
    search_probe = {"returncode": None, "stdout": "", "stderr": "hits_file_reused"}
    if not args.hits.exists():
        search_probe = run_search(config, args.hits, args.threads, max(args.max_hits_per_target, 256))
    sequences = parse_fasta(args.targets_fasta)
    targets = load_jsonl(args.targets_jsonl)
    hits_by_query = load_hits(args.hits)
    db_cfg = config.get("homolog_database") or {}
    source_database = db_cfg.get("database_name") or "UniProtKB/Swiss-Prot"
    database_version = db_cfg.get("database_version") or ""

    intake_rows = []
    missing_hit_targets = []
    for target in targets:
        uniprot_id = str(target.get("uniprot_id") or "")
        sequence = sequences.get(uniprot_id, "")
        target_hits = hits_by_query.get(uniprot_id, [])
        if not sequence or not target_hits:
            missing_hit_targets.append(uniprot_id)
            continue
        intake_rows.append(build_cache_for_target(
            uniprot_id,
            sequence,
            target_hits,
            args.max_hits_per_target,
            args.msa_root,
            args.conservation_root,
            source_database,
            database_version,
        ))
    args.intake_output.parent.mkdir(parents=True, exist_ok=True)
    args.intake_output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in intake_rows), encoding="utf-8")

    total_raw_hits = sum(len(rows) for rows in hits_by_query.values())
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "local_only": True,
        "targets": len(targets),
        "targets_with_hits": len(intake_rows),
        "targets_missing_hits": missing_hit_targets,
        "raw_hit_rows": total_raw_hits,
        "max_hits_per_target": args.max_hits_per_target,
        "hits": str(args.hits.relative_to(AI_ROOT) if args.hits.is_absolute() else args.hits),
        "hits_sha256": sha256(args.hits) if args.hits.exists() else None,
        "intake_output": str(args.intake_output.relative_to(AI_ROOT) if args.intake_output.is_absolute() else args.intake_output),
        "ready_to_apply_trusted_cache_intake": len(intake_rows) == len(targets) and bool(targets),
        "search_probe": search_probe,
        "policy": "MSA/conservation cache is built from real MMseqs2 Swiss-Prot alignments; final manifest validator remains authoritative.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "targets": report["targets"],
        "targets_with_hits": report["targets_with_hits"],
        "raw_hit_rows": report["raw_hit_rows"],
        "ready_to_apply_trusted_cache_intake": report["ready_to_apply_trusted_cache_intake"],
        "output": str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
