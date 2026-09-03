#!/usr/bin/env python3
"""Sync one benchmark case bundle into deploy_data and optional Foldseek indices.

Example:
  python3 scripts/sync_benchmark_case.py --case-id venus-15b --rebuild-foldseek
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = PROJECT_ROOT / "backend" / "app" / "data" / "fixtures" / "benchmark_cases"
STRUCTURE_EXTENSIONS = {".pdb", ".ent", ".cif"}
MAPPING_EXTENSIONS = {".json", ".xml", ".tsv"}
ANNOTATION_EXTENSIONS = {".json", ".jsonl", ".csv", ".tsv", ".txt"}
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".md", ".txt"}


def _load_case(case_id: str) -> dict[str, object]:
    fixture = FIXTURE_ROOT / f"{case_id.replace('-', '_')}.json"
    if not fixture.exists():
        raise SystemExit(f"Benchmark fixture not found: {fixture}")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid fixture JSON: {fixture}")
    return payload


def _matches(path: Path, extensions: set[str]) -> bool:
    suffixes = [part.lower() for part in path.suffixes]
    if not suffixes:
        return False
    if suffixes[-1] in extensions:
        return True
    return len(suffixes) >= 2 and suffixes[-1] == ".gz" and suffixes[-2] in extensions


def _copy_if_needed(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == source.stat().st_size and int(target.stat().st_mtime) >= int(source.stat().st_mtime):
        return False
    shutil.copy2(source, target)
    return True


def _copy_tree_files(source_root: Path, target_root: Path, extensions: set[str]) -> int:
    if not source_root.exists():
        target_root.mkdir(parents=True, exist_ok=True)
        return 0
    target_root.mkdir(parents=True, exist_ok=True)
    copied = 0
    for candidate in sorted(source_root.rglob("*")):
        if not candidate.is_file() or not _matches(candidate, extensions):
            continue
        relative = candidate.relative_to(source_root)
        if _copy_if_needed(candidate, target_root / relative):
            copied += 1
    return copied


def _run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _remove_existing_contents(root: Path) -> None:
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return
    for candidate in root.iterdir():
        if candidate.is_dir():
            shutil.rmtree(candidate)
        else:
            candidate.unlink()


def _copy_tree_all(source_root: Path, target_root: Path) -> int:
    if not source_root.exists():
        target_root.mkdir(parents=True, exist_ok=True)
        return 0
    copied = 0
    for candidate in sorted(source_root.rglob("*")):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(source_root)
        if _copy_if_needed(candidate, target_root / relative):
            copied += 1
    return copied


def _write_bundle_manifest(
    target_file: Path,
    case_id: str,
    deploy_structure: Path,
    deploy_alphafold: Path,
    deploy_sifts: Path,
    deploy_annotations: Path,
    source_bundle_dir: Path,
    incoming_reference_docs: Path,
    discovery_report: Path,
) -> None:
    def _count_files(root: Path) -> int:
        return sum(1 for candidate in root.rglob("*") if candidate.is_file()) if root.exists() else 0

    payload = {
        "case_id": case_id,
        "generated_from": {
            "source_bundle_dir": str(source_bundle_dir),
            "incoming_reference_docs_dir": str(incoming_reference_docs),
            "discovery_report_file": str(discovery_report),
        },
        "bundle_contents": {
            "core_source_files": _count_files(target_file.parent / "source"),
            "reference_docs": _count_files(target_file.parent / "docs" / "reference"),
            "pdb_assets": _count_files(target_file.parent / "assets" / "pdb"),
            "alphafold_assets": _count_files(target_file.parent / "assets" / "alphafold"),
            "sifts_assets": _count_files(target_file.parent / "assets" / "sifts"),
            "annotation_assets": _count_files(target_file.parent / "assets" / "annotations"),
        },
        "deploy_references": {
            "deploy_structure_file": str(deploy_structure),
            "deploy_alphafold_dir": str(deploy_alphafold),
            "deploy_sifts_dir": str(deploy_sifts),
            "deploy_annotations_dir": str(deploy_annotations),
        },
    }
    target_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_bundle_readme(bundle_root: Path, case: dict[str, object]) -> None:
    lines = [
        f"# {case.get('title', case.get('id', 'benchmark-case'))}",
        "",
        f"Case ID: `{case.get('id', '')}`",
        "",
        "This directory is a portable benchmark bundle generated from the local case package plus staged deploy_data assets.",
        "",
        "Contents:",
        "",
        "- `source/`: original case files copied from the case bundle",
        "- `docs/reference/`: optional reference documents selected for this case",
        "- `assets/pdb/`: staged structure assets for this case",
        "- `assets/alphafold/`: staged AlphaFold assets for this case",
        "- `assets/sifts/`: staged SIFTS assets for this case",
        "- `assets/annotations/`: staged annotation assets for this case",
        "- `bundle_manifest.json`: bundle inventory",
        "",
    ]
    (bundle_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _build_bundle(case: dict[str, object], case_id: str, paths: dict[str, object]) -> dict[str, int]:
    source_bundle_dir = PROJECT_ROOT / str(paths.get("source_bundle_dir", ""))
    incoming_reference_docs = PROJECT_ROOT / str(paths.get("incoming_reference_docs_dir", ""))
    discovery_report = PROJECT_ROOT / str(paths.get("discovery_report_file", ""))
    deploy_structure = PROJECT_ROOT / str(paths.get("deploy_structure_file", ""))
    deploy_alphafold = PROJECT_ROOT / str(paths.get("deploy_alphafold_dir", ""))
    deploy_sifts = PROJECT_ROOT / str(paths.get("deploy_sifts_dir", ""))
    deploy_annotations = PROJECT_ROOT / str(paths.get("deploy_annotations_dir", ""))
    bundle_root = PROJECT_ROOT / str(paths.get("deploy_bundle_dir", ""))
    bundle_manifest = PROJECT_ROOT / str(paths.get("deploy_bundle_manifest_file", ""))

    _remove_existing_contents(bundle_root)
    (bundle_root / "source").mkdir(parents=True, exist_ok=True)
    (bundle_root / "docs" / "reference").mkdir(parents=True, exist_ok=True)
    (bundle_root / "assets" / "pdb").mkdir(parents=True, exist_ok=True)
    (bundle_root / "assets" / "alphafold").mkdir(parents=True, exist_ok=True)
    (bundle_root / "assets" / "sifts").mkdir(parents=True, exist_ok=True)
    (bundle_root / "assets" / "annotations").mkdir(parents=True, exist_ok=True)

    source_copied = _copy_tree_files(source_bundle_dir, bundle_root / "source", STRUCTURE_EXTENSIONS | ANNOTATION_EXTENSIONS | DOC_EXTENSIONS)
    reference_copied = _copy_tree_files(incoming_reference_docs, bundle_root / "docs" / "reference", DOC_EXTENSIONS)
    pdb_copied = _copy_if_needed(deploy_structure, bundle_root / "assets" / "pdb" / deploy_structure.name)
    alphafold_copied = _copy_tree_all(deploy_alphafold, bundle_root / "assets" / "alphafold")
    sifts_copied = _copy_tree_all(deploy_sifts, bundle_root / "assets" / "sifts")
    annotations_copied = _copy_tree_all(deploy_annotations, bundle_root / "assets" / "annotations")
    if discovery_report.exists():
        _copy_if_needed(discovery_report, bundle_root / "docs" / "asset_inventory.json")

    _write_bundle_manifest(
        bundle_manifest,
        case_id=case_id,
        deploy_structure=deploy_structure,
        deploy_alphafold=deploy_alphafold,
        deploy_sifts=deploy_sifts,
        deploy_annotations=deploy_annotations,
        source_bundle_dir=source_bundle_dir,
        incoming_reference_docs=incoming_reference_docs,
        discovery_report=discovery_report,
    )
    _write_bundle_readme(bundle_root, case)

    return {
        "source_files": source_copied,
        "reference_docs": reference_copied,
        "pdb_assets": 1 if pdb_copied else 0,
        "alphafold_assets": alphafold_copied,
        "sifts_assets": sifts_copied,
        "annotation_assets": annotations_copied,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True, help="Benchmark case id, e.g. venus-15b")
    parser.add_argument("--rebuild-foldseek", action="store_true", help="Rebuild relevant Foldseek databases after sync")
    args = parser.parse_args()

    case = _load_case(args.case_id)
    paths = case.get("paths")
    if not isinstance(paths, dict):
        raise SystemExit("Fixture missing 'paths'")

    source_bundle_dir = PROJECT_ROOT / str(paths.get("source_bundle_dir", ""))
    source_structure = PROJECT_ROOT / str(paths.get("original_structure_file", ""))
    deploy_structure = PROJECT_ROOT / str(paths.get("deploy_structure_file", ""))
    incoming_alphafold = PROJECT_ROOT / str(paths.get("incoming_alphafold_dir", ""))
    incoming_sifts = PROJECT_ROOT / str(paths.get("incoming_sifts_dir", ""))
    incoming_annotations = PROJECT_ROOT / str(paths.get("incoming_annotations_dir", ""))
    incoming_reference_docs = PROJECT_ROOT / str(paths.get("incoming_reference_docs_dir", ""))
    deploy_alphafold = PROJECT_ROOT / str(paths.get("deploy_alphafold_dir", ""))
    deploy_sifts = PROJECT_ROOT / str(paths.get("deploy_sifts_dir", ""))
    deploy_annotations = PROJECT_ROOT / str(paths.get("deploy_annotations_dir", ""))

    if not source_bundle_dir.exists():
        raise SystemExit(f"Source bundle not found: {source_bundle_dir}")

    for directory in (incoming_alphafold, incoming_sifts, incoming_annotations, incoming_reference_docs, deploy_alphafold, deploy_sifts, deploy_annotations):
        directory.mkdir(parents=True, exist_ok=True)

    pdb_copied = _copy_if_needed(source_structure, deploy_structure)
    alphafold_copied = _copy_tree_files(incoming_alphafold, deploy_alphafold, STRUCTURE_EXTENSIONS | {".json"})
    sifts_copied = _copy_tree_files(incoming_sifts, deploy_sifts, MAPPING_EXTENSIONS)
    annotations_copied = _copy_tree_files(incoming_annotations, deploy_annotations, ANNOTATION_EXTENSIONS)
    bundle_stats = _build_bundle(case, args.case_id, paths)

    print(f"Case: {args.case_id}")
    print(f"Source bundle: {source_bundle_dir}")
    print(f"PDB staged: {deploy_structure.exists()} (copied={pdb_copied})")
    print(f"AlphaFold files copied: {alphafold_copied}")
    print(f"SIFTS files copied: {sifts_copied}")
    print(f"Annotation files copied: {annotations_copied}")
    print(f"Bundle stats: {json.dumps(bundle_stats, ensure_ascii=False)}")

    if args.rebuild_foldseek:
        _run([sys.executable, "scripts/build_foldseek_db.py", "--kind", "pdb"])
        if any(candidate.is_file() and _matches(candidate, STRUCTURE_EXTENSIONS) for candidate in deploy_alphafold.rglob("*")):
            _run([sys.executable, "scripts/build_foldseek_db.py", "--kind", "alphafold"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
