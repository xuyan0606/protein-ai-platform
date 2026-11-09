#!/usr/bin/env python3
"""Inspect deploy_data contents and report whether live data is ready to wire in.

This script does not boot the app or import backend settings. It is intended as
an operator-facing preflight check before running backend readiness/smoke
scripts.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "deploy_data"
SUPPORTED_TABULAR_SUFFIXES = (".json", ".csv", ".tsv")
STRUCTURE_SUFFIXES = (".pdb", ".ent", ".cif", ".pdb.gz", ".cif.gz")
FOLDSEEK_SUBDIRS = ("pdb", "alphafold", "custom")
DEMO_ANNOTATION_SOURCE_DB = "local_demo"
DEMO_SIFTS_FILENAMES = {"1abc.json"}
LIVE_COMPONENTS = ("annotations", "sifts", "pdb", "alphafold", "foldseek", "smoke_query")
LEGACY_LIVE_COMPONENTS = ("annotations", "sifts", "foldseek", "smoke_query")


@dataclass
class CheckResult:
    label: str
    status: str
    detail: str
    expected_count: int | None = None
    actual_count: int | None = None
    missing_items: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    version: str | None = None
    updated_at: str | None = None
    planned_commands: list[str] = field(default_factory=list)


def _existing_files(path: Path, suffixes: tuple[str, ...] | None = None) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        if suffixes is None or path.suffix.lower() in suffixes:
            return [path]
        return []
    matches: list[Path] = []
    for candidate in path.rglob("*"):
        if not candidate.is_file():
            continue
        if suffixes is not None and candidate.suffix.lower() not in suffixes:
            continue
        matches.append(candidate)
    return sorted(matches)


def _file_matches_suffix(path: Path, suffixes: tuple[str, ...]) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in suffixes)


def _latest_mtime(files: list[Path]) -> str | None:
    latest = 0.0
    for path in files:
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    if latest <= 0:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()


def _sample_details(files: list[Path], limit: int = 3) -> str:
    if not files:
        return "0 files"
    names = ", ".join(path.name for path in files[:limit])
    if len(files) > limit:
        names += f", ... (+{len(files) - limit} more)"
    return f"{len(files)} files: {names}"


def _find_nonportable_symlinks(path: Path) -> list[str]:
    if not path.exists():
        return []
    issues: list[str] = []
    for candidate in sorted(path.rglob("*")):
        if not candidate.is_symlink():
            continue
        target_text = str(candidate.readlink())
        if Path(target_text).is_absolute():
            issues.append(f"{candidate.relative_to(path)} -> {target_text}")
            continue
        resolved = (candidate.parent / target_text).resolve(strict=False)
        if not resolved.exists():
            issues.append(f"{candidate.relative_to(path)} -> {target_text} (broken)")
    return issues


def _load_json(path: Path) -> dict[str, object] | list[object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_manifest(root: Path) -> dict[str, object]:
    path = root / "live_manifest.json"
    payload = _load_json(path) if path.exists() else None
    if isinstance(payload, dict):
        return payload
    return {}


def _string_list(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key) or []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        normalized = text.upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _manifest_version(manifest: dict[str, object]) -> str | None:
    for key in ("data_version", "version", "updated_at", "generated_at", "created_at"):
        value = manifest.get(key)
        if value:
            return str(value)
    return None


def _expected_dataset(manifest: dict[str, object], name: str) -> dict[str, object]:
    datasets = manifest.get("expected_datasets")
    if isinstance(datasets, dict):
        value = datasets.get(name)
        if isinstance(value, dict):
            return value
    return {}


def _planned_commands(manifest: dict[str, object], name: str) -> list[str]:
    dataset = _expected_dataset(manifest, name)
    commands = dataset.get("plan_only_commands") or dataset.get("commands") or []
    if not isinstance(commands, list):
        return []
    return [str(item) for item in commands if str(item).strip()]


def _required_components(manifest: dict[str, object]) -> tuple[str, ...]:
    value = manifest.get("required_live_components")
    if isinstance(value, list):
        names = [str(item).strip() for item in value if str(item).strip()]
        known = tuple(name for name in names if name in LIVE_COMPONENTS)
        if known:
            return known
    return LIVE_COMPONENTS


def _expected_count(manifest: dict[str, object], name: str) -> int | None:
    dataset = _expected_dataset(manifest, name)
    value = dataset.get("expected_count")
    try:
        count = int(value) if value is not None else 0
    except (TypeError, ValueError):
        count = 0
    return count if count > 0 else None


def _missing_expected_ids(expected_ids: list[str], files: list[Path], *, aliases: dict[str, list[str]] | None = None) -> list[str]:
    names = [path.name.lower() for path in files]
    missing: list[str] = []
    for expected_id in expected_ids:
        candidates = [expected_id.lower()]
        if aliases and expected_id in aliases:
            candidates.extend(alias.lower() for alias in aliases[expected_id])
        if not any(any(candidate in name for candidate in candidates) for name in names):
            missing.append(expected_id)
    return missing


def _dataset_next_action(name: str, missing_items: list[str]) -> list[str]:
    if not missing_items:
        return []
    if name == "annotations":
        return ["Stage real UniProt/InterPro/M-CSA/SignalP exports or run download_real_annotations.py on a network-enabled host."]
    if name == "sifts":
        return ["Stage PDBe/SIFTS residue mapping files for the manifest PDB IDs."]
    if name == "pdb":
        return ["Stage RCSB PDB/mmCIF structures for the manifest PDB IDs."]
    if name == "alphafold":
        return ["Stage AlphaFold structures and requested JSON companions for the manifest UniProt IDs."]
    if name == "foldseek":
        return ["Build or stage Foldseek DBs for PDB and AlphaFold, then materialize symlinks before container deployment."]
    if name == "smoke_query":
        return ["Place a representative query structure at deploy_data/smoke/query.pdb."]
    return ["Stage the missing live data and rerun this check."]


def _annotation_state(path: Path, files: list[Path]) -> tuple[str, str]:
    metadata = path / "metadata.json"
    payload = _load_json(metadata) if metadata.exists() else None
    if isinstance(payload, dict) and payload.get("default_source_db") == DEMO_ANNOTATION_SOURCE_DB:
        return "demo", _sample_details(files)
    return "ready", _sample_details(files)


def _sifts_state(files: list[Path]) -> tuple[str, str]:
    names = {path.name for path in files}
    if names and names.issubset(DEMO_SIFTS_FILENAMES):
        return "demo", _sample_details(files)
    return "ready", _sample_details(files)


def _check_annotations(root: Path, manifest: dict[str, object]) -> CheckResult:
    path = root / "annotations"
    files = _existing_files(path, SUPPORTED_TABULAR_SUFFIXES)
    expected_count = _expected_count(manifest, "annotations")
    if not files:
        return CheckResult(
            "annotations",
            "missing",
            f"{path} (expected base/interpro/mcsa/signalp as json/csv/tsv)",
            actual_count=0,
            missing_items=["base/interpro/mcsa/signalp annotation exports"],
            next_actions=_dataset_next_action("annotations", ["annotation exports"]),
            version=_manifest_version(manifest),
            planned_commands=_planned_commands(manifest, "annotations"),
        )
    status, detail = _annotation_state(path, files)
    missing_items = ["replace demo annotations with live exports"] if status == "demo" else []
    if status == "ready" and expected_count and len(files) < expected_count:
        status = "partial"
        missing_items.append(f"annotation exports expected>={expected_count} actual={len(files)}")
    return CheckResult(
        "annotations",
        status,
        detail,
        expected_count=expected_count,
        actual_count=len(files),
        missing_items=missing_items,
        next_actions=_dataset_next_action("annotations", missing_items),
        version=_manifest_version(manifest),
        updated_at=_latest_mtime(files),
        planned_commands=_planned_commands(manifest, "annotations"),
    )


def _check_sifts(root: Path, manifest: dict[str, object]) -> CheckResult:
    path = root / "sifts"
    files = _existing_files(path, SUPPORTED_TABULAR_SUFFIXES)
    expected_ids = _string_list(manifest, "pdb_ids")
    if not files:
        return CheckResult(
            "sifts",
            "missing",
            f"{path} (expected mapping json/csv/tsv exports)",
            expected_count=len(expected_ids) or None,
            actual_count=0,
            missing_items=expected_ids or ["SIFTS mapping exports"],
            next_actions=_dataset_next_action("sifts", expected_ids or ["mapping exports"]),
            version=_manifest_version(manifest),
            planned_commands=_planned_commands(manifest, "sifts"),
        )
    status, detail = _sifts_state(files)
    missing_items = _missing_expected_ids(expected_ids, files) if expected_ids and status == "ready" else []
    if status == "demo":
        missing_items = expected_ids or ["replace demo SIFTS mapping with live exports"]
    return CheckResult(
        "sifts",
        status,
        detail,
        expected_count=len(expected_ids) or None,
        actual_count=len(files),
        missing_items=missing_items,
        next_actions=_dataset_next_action("sifts", missing_items),
        version=_manifest_version(manifest),
        updated_at=_latest_mtime(files),
        planned_commands=_planned_commands(manifest, "sifts"),
    )


def _check_pdb(root: Path, manifest: dict[str, object]) -> CheckResult:
    path = root / "pdb"
    files = _existing_files(path)
    structure_files = [item for item in files if _file_matches_suffix(item, STRUCTURE_SUFFIXES)]
    expected_ids = _string_list(manifest, "pdb_ids")
    if not structure_files:
        return CheckResult(
            "pdb",
            "missing",
            f"{path} (expected PDB/mmCIF structures)",
            expected_count=len(expected_ids) or None,
            actual_count=0,
            missing_items=expected_ids or ["PDB/mmCIF structure files"],
            next_actions=_dataset_next_action("pdb", expected_ids or ["structure files"]),
            version=_manifest_version(manifest),
            planned_commands=_planned_commands(manifest, "pdb"),
        )
    missing_items = _missing_expected_ids(expected_ids, structure_files) if expected_ids else []
    status = "partial" if missing_items else "ready"
    return CheckResult(
        "pdb",
        status,
        _sample_details(structure_files),
        expected_count=len(expected_ids) or None,
        actual_count=len(structure_files),
        missing_items=missing_items,
        next_actions=_dataset_next_action("pdb", missing_items),
        version=_manifest_version(manifest),
        updated_at=_latest_mtime(structure_files),
        planned_commands=_planned_commands(manifest, "pdb"),
    )


def _check_alphafold(root: Path, manifest: dict[str, object]) -> CheckResult:
    path = root / "alphafold"
    files = _existing_files(path)
    structure_files = [item for item in files if _file_matches_suffix(item, STRUCTURE_SUFFIXES)]
    expected_ids = _string_list(manifest, "uniprot_ids")
    aliases = {item: [f"AF-{item}-F1"] for item in expected_ids}
    missing_structures = _missing_expected_ids(expected_ids, structure_files, aliases=aliases) if expected_ids else []
    missing_pae: list[str] = []
    if bool(manifest.get("download_pae_json", True)) and expected_ids:
        json_files = [item for item in files if item.suffix.lower() == ".json"]
        missing_pae = _missing_expected_ids(expected_ids, json_files, aliases=aliases)
    missing_items = [f"structure:{item}" for item in missing_structures] + [f"pae_json:{item}" for item in missing_pae]
    if not structure_files:
        missing_items = missing_items or expected_ids or ["AlphaFold CIF/PDB model files"]
        return CheckResult(
            "alphafold",
            "missing",
            f"{path} (expected AlphaFold CIF/PDB structures)",
            expected_count=len(expected_ids) or None,
            actual_count=0,
            missing_items=missing_items,
            next_actions=_dataset_next_action("alphafold", missing_items),
            version=_manifest_version(manifest),
            planned_commands=_planned_commands(manifest, "alphafold"),
        )
    status = "partial" if missing_items else "ready"
    return CheckResult(
        "alphafold",
        status,
        _sample_details(structure_files),
        expected_count=len(expected_ids) or None,
        actual_count=len(structure_files),
        missing_items=missing_items,
        next_actions=_dataset_next_action("alphafold", missing_items),
        version=_manifest_version(manifest),
        updated_at=_latest_mtime(files),
        planned_commands=_planned_commands(manifest, "alphafold"),
    )


def _check_foldseek(root: Path, manifest: dict[str, object]) -> CheckResult:
    endpoint = os.getenv("FOLDSEEK_API_URL", "").strip()
    if endpoint:
        return CheckResult(
            "foldseek",
            "ready",
            f"http endpoint: {endpoint}",
            planned_commands=_planned_commands(manifest, "foldseek"),
        )

    foldseek_root = root / "foldseek"
    dataset = _expected_dataset(manifest, "foldseek")
    required_subdatabases = dataset.get("expected_subdatabases")
    if not isinstance(required_subdatabases, list) or not required_subdatabases:
        required_subdatabases = ["pdb", "alphafold"]
    details: list[str] = []
    ready_sources = 0
    missing_subdatabases: list[str] = []
    for name in FOLDSEEK_SUBDIRS:
        files = _existing_files(foldseek_root / name)
        if not files:
            if name in required_subdatabases:
                missing_subdatabases.append(name)
            continue
        ready_sources += 1
        details.append(f"{name}={_sample_details(files, limit=1)}")

    if not ready_sources:
        return CheckResult(
            "foldseek",
            "missing",
            f"{foldseek_root} (populate pdb/alphafold/custom or set FOLDSEEK_API_URL)",
            actual_count=0,
            missing_items=["foldseek/pdb DB", "foldseek/alphafold DB"],
            next_actions=_dataset_next_action("foldseek", ["foldseek DB"]),
            version=_manifest_version(manifest),
            planned_commands=_planned_commands(manifest, "foldseek"),
        )
    portability_issues = _find_nonportable_symlinks(foldseek_root)
    if portability_issues:
        sample = "; ".join(portability_issues[:2])
        if len(portability_issues) > 2:
            sample += f"; ... (+{len(portability_issues) - 2} more)"
        return CheckResult(
            "foldseek",
            "partial",
            (
                f"non-portable symlinks detected: {sample}. "
                "Run python scripts/materialize_foldseek_links.py before Docker deployment."
            ),
            missing_items=portability_issues,
            next_actions=["Run python scripts/materialize_foldseek_links.py --root deploy_data/foldseek before Docker deployment."],
            version=_manifest_version(manifest),
            planned_commands=_planned_commands(manifest, "foldseek"),
        )
    files = _existing_files(foldseek_root)
    if missing_subdatabases:
        return CheckResult(
            "foldseek",
            "partial",
            "; ".join(details) if details else f"{foldseek_root} has no required subdatabases",
            actual_count=len(files),
            missing_items=[f"foldseek/{name} DB" for name in missing_subdatabases],
            next_actions=_dataset_next_action("foldseek", missing_subdatabases),
            version=_manifest_version(manifest),
            updated_at=_latest_mtime(files),
            planned_commands=_planned_commands(manifest, "foldseek"),
        )
    return CheckResult(
        "foldseek",
        "ready",
        "; ".join(details),
        actual_count=len(files),
        version=_manifest_version(manifest),
        updated_at=_latest_mtime(files),
        planned_commands=_planned_commands(manifest, "foldseek"),
    )


def _check_smoke_query(root: Path, manifest: dict[str, object]) -> CheckResult:
    path = root / "smoke" / "query.pdb"
    if not path.exists():
        return CheckResult(
            "smoke_query",
            "missing",
            str(path),
            actual_count=0,
            missing_items=["smoke/query.pdb"],
            next_actions=_dataset_next_action("smoke_query", ["smoke/query.pdb"]),
            version=_manifest_version(manifest),
            planned_commands=_planned_commands(manifest, "smoke_query"),
        )
    size = path.stat().st_size
    return CheckResult(
        "smoke_query",
        "ready",
        f"{path.name} ({size} bytes)",
        actual_count=1,
        version=_manifest_version(manifest),
        updated_at=_latest_mtime([path]),
        planned_commands=_planned_commands(manifest, "smoke_query"),
    )


def _check_root(root: Path) -> CheckResult:
    if root.exists():
        return CheckResult("deploy_data_root", "ready", str(root))
    return CheckResult("deploy_data_root", "missing", str(root))


def _summarize(results: list[CheckResult], manifest: dict[str, object]) -> CheckResult:
    statuses = {result.label: result.status for result in results}
    if statuses["deploy_data_root"] != "ready":
        return CheckResult("summary", "empty", "Create deploy_data first: python scripts/prepare_deploy_data.py")
    has_demo_assets = any(statuses[label] == "demo" for label in ("annotations", "sifts"))
    if has_demo_assets:
        missing_items: list[str] = []
        next_actions: list[str] = []
        for result in results:
            if result.label in LIVE_COMPONENTS and result.status != "ready":
                missing_items.extend(f"{result.label}:{item}" for item in (result.missing_items or [result.detail]))
                next_actions.extend(result.next_actions)
        return CheckResult(
            "summary",
            "demo-data-only",
            "Demo assets detected. Import real annotations/SIFTS/Foldseek data before expecting live-ready.",
            missing_items=missing_items,
            next_actions=next_actions,
        )
    if not manifest:
        return CheckResult(
            "summary",
            "partial",
            "Add deploy_data/live_manifest.json before evaluating live data readiness",
            missing_items=["deploy_data/live_manifest.json"],
            next_actions=["Create or stage live_manifest.json with expected live components and dataset IDs."],
        )
    required_components = _required_components(manifest)
    live_data_ready = all(statuses[label] == "ready" for label in required_components)
    missing_items: list[str] = []
    next_actions: list[str] = []
    for result in results:
        if result.label in required_components and result.status != "ready":
            missing_items.extend(f"{result.label}:{item}" for item in (result.missing_items or [result.detail]))
            next_actions.extend(result.next_actions)
    if live_data_ready:
        return CheckResult(
            "summary",
            "live-data-ready",
            "Next: cd backend && .venv/bin/python scripts/structure_smoke_readiness.py",
        )
    return CheckResult(
        "summary",
        "partial",
        "Add missing real datasets, then run backend/scripts/structure_smoke_readiness.py",
        missing_items=missing_items,
        next_actions=next_actions,
    )


def _version_comparison(root: Path, manifest: dict[str, object], results: list[CheckResult]) -> CheckResult:
    manifest_path = root / "live_manifest.json"
    version = _manifest_version(manifest)
    if not manifest:
        return CheckResult(
            "version_comparison",
            "missing",
            f"No live manifest found at {manifest_path}",
            missing_items=["deploy_data/live_manifest.json"],
            next_actions=["Create or update deploy_data/live_manifest.json before a live refresh."],
        )
    component_versions = [
        f"{item.label}:{item.actual_count or 0}:{item.updated_at or 'unknown'}"
        for item in results
        if item.label in LIVE_COMPONENTS
    ]
    return CheckResult(
        "version_comparison",
        "planned" if any(item.status != "ready" for item in results if item.label in LIVE_COMPONENTS) else "current",
        f"manifest={version or 'unknown'}; components={', '.join(component_versions)}",
        version=version,
        updated_at=str(manifest.get("updated_at") or "") or None,
    )


def _dry_run_plan(manifest: dict[str, object], results: list[CheckResult]) -> CheckResult:
    commands: list[str] = []
    for result in results:
        commands.extend(result.planned_commands)
    if not commands:
        commands = [
            "python3 scripts/run_deploy_data_update.py --plan-only --json",
            "python3 scripts/check_deploy_data.py --json",
        ]
    missing = [result.label for result in results if result.label in LIVE_COMPONENTS and result.status != "ready"]
    detail = "No downloads or writes performed. "
    detail += "Missing/not-ready components: " + (", ".join(missing) if missing else "none")
    return CheckResult(
        "dry_run",
        "planned",
        detail,
        version=_manifest_version(manifest),
        planned_commands=commands,
    )


def _collect_results(root: Path) -> list[CheckResult]:
    manifest = _load_manifest(root)
    results = [
        _check_root(root),
        _check_annotations(root, manifest),
        _check_sifts(root, manifest),
        _check_pdb(root, manifest),
        _check_alphafold(root, manifest),
        _check_foldseek(root, manifest),
        _check_smoke_query(root, manifest),
    ]
    results.append(_version_comparison(root, manifest, results))
    results.append(_dry_run_plan(manifest, results))
    results.append(_summarize(results, manifest))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="deploy_data root to inspect")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="Exit non-zero unless summary reaches live-data-ready.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Explicitly emit the read-only missing-data and next-action plan. No downloads or writes are performed.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    results = _collect_results(root)

    if args.json:
        print(json.dumps([asdict(item) for item in results], ensure_ascii=True, indent=2))
    else:
        for item in results:
            suffixes: list[str] = []
            if item.missing_items:
                suffixes.append(f"missing={','.join(item.missing_items[:8])}")
            if item.next_actions:
                suffixes.append(f"next={item.next_actions[0]}")
            if args.plan_only and item.planned_commands:
                suffixes.append(f"plan={' | '.join(item.planned_commands[:4])}")
            suffix = f"\t{'; '.join(suffixes)}" if suffixes else ""
            print(f"{item.label}\t{item.status}\t{item.detail}{suffix}")
    summary = next((item for item in results if item.label == "summary"), None)
    if args.require_live and summary is not None and summary.status != "live-data-ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
