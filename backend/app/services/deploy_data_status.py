"""Deploy-data readiness inspection for operator and data-management views."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT, settings

STRUCTURE_EXTENSIONS = {".pdb", ".ent", ".cif", ".pdb.gz", ".cif.gz"}
MAPPING_EXTENSIONS = {".json", ".xml", ".tsv", ".csv", ".gz"}
ANNOTATION_EXTENSIONS = {".json", ".jsonl", ".csv", ".tsv", ".txt"}


def _path_info(path: Path) -> dict[str, Any]:
    try:
        relative = str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        relative = str(path)
    return {
        "path": str(path),
        "project_relative_path": relative,
        "exists": path.exists(),
    }


def _matches(path: Path, extensions: set[str]) -> bool:
    lowered = path.name.lower()
    return any(lowered.endswith(ext) for ext in extensions)


def _collect_files(root: Path, extensions: set[str], limit: int = 8) -> tuple[int, int, list[dict[str, Any]]]:
    if not root.exists() or not root.is_dir():
        return 0, 0, []

    count = 0
    total_size = 0
    preview: list[dict[str, Any]] = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file() or not _matches(candidate, extensions):
            continue
        count += 1
        try:
            size = candidate.stat().st_size
        except OSError:
            size = 0
        total_size += size
        if len(preview) < limit:
            item = _path_info(candidate)
            item["size_bytes"] = size
            preview.append(item)
    return count, total_size, preview


def _latest_updated_at(preview: list[dict[str, Any]] | dict[str, list[dict[str, Any]]]) -> str | None:
    paths: list[str] = []
    if isinstance(preview, list):
        paths = [str(item.get("path") or "") for item in preview if isinstance(item, dict)]
    elif isinstance(preview, dict):
        for items in preview.values():
            paths.extend(str(item.get("path") or "") for item in items if isinstance(item, dict))
    latest = 0.0
    for raw_path in paths:
        path = Path(raw_path)
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    if latest <= 0:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(latest, tz=timezone.utc).isoformat()


def _component_version(name: str, count: int, updated_at: str | None) -> str | None:
    if count <= 0:
        return None
    return f"{name}:{count}:{updated_at or 'unknown'}"


def _missing_items_for_component(status: str, *, expected: list[str], demo: bool = False) -> list[str]:
    if status == "ready":
        return []
    if demo:
        return ["replace demo files with live exports"]
    return expected


def _enrich_component_metadata(
    component: dict[str, Any],
    *,
    name: str,
    count: int,
    expected: list[str],
    demo: bool = False,
) -> dict[str, Any]:
    updated_at = _latest_updated_at(component.get("preview") or [])
    component["updated_at"] = updated_at
    component["version"] = _component_version(name, count, updated_at)
    component["missing_items"] = _missing_items_for_component(str(component.get("status") or ""), expected=expected, demo=demo)
    return component


def _is_demo_annotations(root: Path) -> bool:
    metadata = root / "metadata.json"
    if not metadata.exists():
        return False
    try:
        payload = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return str(payload.get("default_source_db") or "").lower() == "local_demo"


def _is_demo_sifts(root: Path) -> bool:
    if not root.exists() or not root.is_dir():
        return False
    files = [path.name.lower() for path in root.iterdir() if path.is_file()]
    return bool(files) and set(files).issubset({"1abc.json"})


def _component_status(*, exists: bool, count: int, demo: bool = False) -> str:
    if not exists:
        return "missing"
    if count <= 0:
        return "empty"
    if demo:
        return "demo"
    return "ready"


def _component_failure_reason(status: str, *, label: str, path: Path, count: int, demo: bool = False) -> str | None:
    if status == "ready":
        return None
    if status == "missing":
        return f"{label} path is missing: {path}"
    if status == "empty":
        return f"{label} path exists but no supported files were found."
    if status == "demo" or demo:
        return f"{label} currently contains demo data and is not live-ready."
    return f"{label} is not ready."


def _with_failure_reason(component: dict[str, Any], *, label: str, path: Path, count: int, demo: bool = False) -> dict[str, Any]:
    status = str(component.get("status") or "unknown")
    component["failure_reason"] = _component_failure_reason(status, label=label, path=path, count=count, demo=demo)
    return component


def _foldseek_component(root: Path) -> dict[str, Any]:
    pdb_root = root / "pdb"
    alphafold_root = root / "alphafold"
    pdb_count, pdb_size, pdb_preview = _collect_files(pdb_root, {".dbtype", ".index", ".lookup", ".source"})
    af_count, af_size, af_preview = _collect_files(alphafold_root, {".dbtype", ".index", ".lookup", ".source"})
    total_count = pdb_count + af_count
    component = {
        "status": _component_status(exists=root.exists(), count=total_count),
        "path": _path_info(root),
        "counts": {
            "pdb_index_files": pdb_count,
            "alphafold_index_files": af_count,
        },
        "size_bytes": pdb_size + af_size,
        "preview": {
            "pdb": pdb_preview,
            "alphafold": af_preview,
        },
    }
    component = _enrich_component_metadata(
        component,
        name="foldseek",
        count=total_count,
        expected=["pdb DB index files", "alphafold DB index files"],
    )
    return _with_failure_reason(component, label="Foldseek DB", path=root, count=total_count)


def _json_summary(path: Path, label: str) -> dict[str, Any]:
    info = _path_info(path)
    info["label"] = label
    info["updated_at"] = None
    info["keys"] = []
    info["size_bytes"] = 0
    info["status"] = "missing"
    info["failure_reason"] = f"Manifest is missing: {path}"
    info["component"] = _manifest_component(label)
    info["version"] = None
    if not path.exists() or not path.is_file():
        return info
    try:
        info["size_bytes"] = path.stat().st_size
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        info["parse_error"] = True
        info["status"] = "parse_error"
        info["failure_reason"] = f"Manifest exists but could not be parsed as JSON: {path}"
        return info
    if isinstance(payload, dict):
        info["updated_at"] = payload.get("updated_at") or payload.get("generated_at") or payload.get("created_at")
        info["keys"] = sorted(str(key) for key in payload.keys())[:20]
        info["counts"] = _manifest_counts(payload)
        info["version"] = payload.get("version") or payload.get("data_version") or payload.get("release") or payload.get("generated_at") or payload.get("created_at")
        info["status"] = "ok"
        info["failure_reason"] = None
    return info


def _manifest_component(label: str) -> str:
    if label == "live_seed_manifest":
        return "live"
    if label == "last_manual_import":
        return "manual_import"
    if label.startswith("benchmark:"):
        return "benchmark"
    return "unknown"


def _manifest_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in ("pdb_ids", "uniprot_ids"):
        value = payload.get(key)
        if isinstance(value, list):
            counts[key] = len(value)
    bundle_contents = payload.get("bundle_contents")
    if isinstance(bundle_contents, dict):
        for key, value in bundle_contents.items():
            try:
                counts[f"bundle_{key}"] = int(value)
            except (TypeError, ValueError):
                continue
    return counts


def _update_history(root: Path) -> dict[str, Any]:
    benchmark_manifests = sorted((root / "benchmarks").glob("*/bundle_manifest.json")) if (root / "benchmarks").exists() else []
    manifests = [
        _json_summary(root / "live_manifest.json", "live_seed_manifest"),
        _json_summary(root / "import-manifest.json", "last_manual_import"),
    ]
    manifests.extend(_json_summary(path, f"benchmark:{path.parent.name}") for path in benchmark_manifests[:12])
    present = [item for item in manifests if item.get("exists")]
    failures = [item for item in manifests if item.get("exists") and item.get("status") != "ok"]
    return {
        "manifest_count": len(present),
        "failure_count": len(failures),
        "manifests": manifests,
        "filters": {
            "components": sorted({str(item.get("component") or "unknown") for item in manifests}),
            "statuses": sorted({str(item.get("status") or "unknown") for item in manifests}),
        },
    }


def _version_comparison(components: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    manifests = [item for item in updates.get("manifests", []) if isinstance(item, dict) and item.get("exists")]
    latest = manifests[0] if manifests else None
    for item in manifests[1:]:
        if str(item.get("updated_at") or "") > str(latest.get("updated_at") or ""):
            latest = item
    ready_components = [name for name, component in components.items() if component.get("status") == "ready"]
    not_ready_components = [name for name, component in components.items() if component.get("status") != "ready"]
    return {
        "latest_manifest": latest,
        "ready_components": ready_components,
        "not_ready_components": not_ready_components,
        "all_components_ready": not bool(not_ready_components),
        "manifest_versions": [
            {
                "label": item.get("label"),
                "component": item.get("component"),
                "version": item.get("version"),
                "updated_at": item.get("updated_at"),
                "status": item.get("status"),
            }
            for item in manifests
        ],
    }


def collect_deploy_data_readiness() -> dict[str, Any]:
    """Return a host/runtime view of deploy_data readiness.

    This is intentionally read-only and filesystem based, so it can back both
    API health views and future admin screens without mutating data.
    """
    root = Path(settings.DEPLOY_DATA_ROOT or PROJECT_ROOT / "deploy_data").expanduser()
    annotations = root / "annotations"
    sifts = root / "sifts"
    pdb = root / "pdb"
    alphafold = root / "alphafold"
    smoke = root / "smoke"
    smoke_query = smoke / "query.pdb"

    annotation_count, annotation_size, annotation_preview = _collect_files(annotations, ANNOTATION_EXTENSIONS)
    sifts_count, sifts_size, sifts_preview = _collect_files(sifts, MAPPING_EXTENSIONS)
    pdb_count, pdb_size, pdb_preview = _collect_files(pdb, STRUCTURE_EXTENSIONS)
    alphafold_count, alphafold_size, alphafold_preview = _collect_files(alphafold, STRUCTURE_EXTENSIONS)
    smoke_count = 1 if smoke_query.exists() and smoke_query.is_file() else 0
    smoke_size = smoke_query.stat().st_size if smoke_count else 0

    annotations_demo = _is_demo_annotations(annotations)
    sifts_demo = _is_demo_sifts(sifts)
    components = {
        "annotations": {
            "status": _component_status(exists=annotations.exists(), count=annotation_count, demo=annotations_demo),
            "path": _path_info(annotations),
            "count": annotation_count,
            "size_bytes": annotation_size,
            "preview": annotation_preview,
        },
        "sifts": {
            "status": _component_status(exists=sifts.exists(), count=sifts_count, demo=sifts_demo),
            "path": _path_info(sifts),
            "count": sifts_count,
            "size_bytes": sifts_size,
            "preview": sifts_preview,
        },
        "pdb": {
            "status": _component_status(exists=pdb.exists(), count=pdb_count),
            "path": _path_info(pdb),
            "count": pdb_count,
            "size_bytes": pdb_size,
            "preview": pdb_preview,
        },
        "alphafold": {
            "status": _component_status(exists=alphafold.exists(), count=alphafold_count),
            "path": _path_info(alphafold),
            "count": alphafold_count,
            "size_bytes": alphafold_size,
            "preview": alphafold_preview,
        },
        "foldseek": _foldseek_component(root / "foldseek"),
        "smoke_query": {
            "status": _component_status(exists=smoke.exists(), count=smoke_count),
            "path": _path_info(smoke_query),
            "count": smoke_count,
            "size_bytes": smoke_size,
            "preview": [_path_info(smoke_query)] if smoke_count else [],
        },
    }
    components["annotations"] = _enrich_component_metadata(
        components["annotations"],
        name="annotations",
        count=annotation_count,
        expected=["UniProt/InterPro/M-CSA/SignalP annotation files"],
        demo=annotations_demo,
    )
    components["sifts"] = _enrich_component_metadata(
        components["sifts"],
        name="sifts",
        count=sifts_count,
        expected=["PDBe SIFTS mapping files"],
        demo=sifts_demo,
    )
    components["pdb"] = _enrich_component_metadata(
        components["pdb"],
        name="pdb",
        count=pdb_count,
        expected=["PDB/mmCIF structure files"],
    )
    components["alphafold"] = _enrich_component_metadata(
        components["alphafold"],
        name="alphafold",
        count=alphafold_count,
        expected=["AlphaFold CIF/PDB model files"],
    )
    components["smoke_query"] = _enrich_component_metadata(
        components["smoke_query"],
        name="smoke_query",
        count=smoke_count,
        expected=["deploy_data/smoke/query.pdb"],
    )
    components["annotations"] = _with_failure_reason(components["annotations"], label="Annotations", path=annotations, count=annotation_count, demo=annotations_demo)
    components["sifts"] = _with_failure_reason(components["sifts"], label="SIFTS", path=sifts, count=sifts_count, demo=sifts_demo)
    components["pdb"] = _with_failure_reason(components["pdb"], label="PDB", path=pdb, count=pdb_count)
    components["alphafold"] = _with_failure_reason(components["alphafold"], label="AlphaFold", path=alphafold, count=alphafold_count)
    components["smoke_query"] = _with_failure_reason(components["smoke_query"], label="Smoke query", path=smoke_query, count=smoke_count)

    required = ["annotations", "sifts", "pdb", "alphafold", "foldseek", "smoke_query"]
    statuses = {name: str(components[name]["status"]) for name in required}
    live_ready = all(status == "ready" for status in statuses.values())
    demo_only = any(status == "demo" for status in statuses.values()) and not live_ready
    missing = [name for name, status in statuses.items() if status in {"missing", "empty", "demo"}]

    if live_ready:
        summary = "live-ready"
    elif demo_only:
        summary = "demo-ready"
    elif any(status == "ready" for status in statuses.values()):
        summary = "partial"
    else:
        summary = "empty"

    updates = _update_history(root)
    return {
        "summary": summary,
        "live_ready": live_ready,
        "root": _path_info(root),
        "components": components,
        "updates": updates,
        "version_comparison": _version_comparison(components, updates),
        "missing_or_demo_components": missing,
        "next_actions": _next_actions(statuses),
    }


def _next_actions(statuses: dict[str, str]) -> list[str]:
    actions: list[str] = []
    if statuses.get("annotations") != "ready":
        actions.append("Import real annotations into deploy_data/annotations.")
    if statuses.get("sifts") != "ready":
        actions.append("Import real SIFTS mappings into deploy_data/sifts.")
    if statuses.get("pdb") != "ready":
        actions.append("Import real PDB/mmCIF structures into deploy_data/pdb.")
    if statuses.get("alphafold") != "ready":
        actions.append("Import AlphaFold CIF/PDB models into deploy_data/alphafold.")
    if statuses.get("foldseek") != "ready":
        actions.append("Build Foldseek databases for PDB and AlphaFold sources.")
    if statuses.get("smoke_query") != "ready":
        actions.append("Place a representative smoke query at deploy_data/smoke/query.pdb.")
    return actions
