"""Data query API — unified access to 10 integrated databases.

Endpoints:
  GET  /search              cross-database full-text search
  GET  /protein/{id}        aggregated protein detail
  GET  /protein/{id}/kinetics
  GET  /protein/{id}/stability
  GET  /protein/{id}/structures
  GET  /protein/{id}/evolution
  GET  /ec/{ec_number}      EC number lookup
  GET  /substrate/{q}       compound search
  GET  /reaction/{rhea_id}  reaction lookup
  GET  /stats               database statistics
  POST /ingest/{source}     trigger data ingestion
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import get_current_user, require_admin
from app.services.experiment_feedback import (
    create_experiment_feedback_record,
    list_experiment_feedback_records,
    summarize_feedback_records,
)
from app.services.wet_lab_calibration import (
    build_calibration_summary,
    create_wet_lab_calibration_run,
    list_wet_lab_calibration_runs,
)
from app.tools.feedback_iteration_planner import feedback_iteration_planner
from app.tools.tool_capability_audit import tool_capability_audit
from app.services.lipase_curation import (
    create_lipase_curation_record,
    create_lipase_curation_batch,
    list_lipase_curation_records,
    list_lipase_curation_batches,
    preview_lipase_curation_batch,
    publish_lipase_curation_batch,
    update_lipase_curation_review,
)
from app.services.project_acl import can_perform_project_action, get_project_access
from app.models.domain import (
    EnzymeRecord,
    ECNumber,
    EnzymeECLink,
    InterProEntry,
    EnzymeInterProLink,
    PDBStructure,
    AlphaFoldStructure,
    KineticParameter,
    StabilityRecord,
    CatalyticSite,
    CatalyticResidue,
    SubstrateCompound,
    ReactionEquation,
    DirectedEvolutionEntry,
    DatabaseCrossRef,
    SignalPeptidePrediction,
    Taxonomy,
    PfamDomain,
    DomainArchitecture,
    KVStore,
)
from app.services.annotation_query_service import AnnotationQueryService
from app.services.reaction_profile import ReactionProfileService
from app.services.deploy_data_status import collect_deploy_data_readiness
from app.services.enzyme_evidence_db import (
    POLICY_DECISION_CONFIRMATION_TOKEN,
    SIMPLE_ENZYME_DATABASES,
    collect_simple_enzyme_db_status,
    list_enzyme_db_families,
    list_simple_enzyme_export_safe_measurements,
    list_simple_enzyme_measurements,
    list_simple_enzyme_papers,
    list_simple_enzyme_variants,
    publish_simple_enzyme_policy_decision_batch,
    preview_simple_enzyme_policy_decision_batch,
    search_simple_enzyme_db,
)
from app.services.enzyme_metadata_curation import (
    archive_enzyme_metadata_curation_batch,
    create_enzyme_metadata_curation_batch,
    list_enzyme_metadata_curation_batches,
    list_enzyme_metadata_curation_records,
    materialize_enzyme_metadata_policy_decisions,
    preview_enzyme_metadata_curation_batch,
    update_enzyme_metadata_curation_review,
)
from app.services.lipase_db_status import (
    build_lipase_evidence_context,
    collect_lipase_db_status,
    get_lipase_paper_detail,
    list_lipase_gaps,
    list_lipase_papers,
    list_lipase_variants,
    search_lipase_evidence,
)

router = APIRouter(tags=["Data"])
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent if BACKEND_ROOT.name == "backend" else BACKEND_ROOT
BENCHMARK_FIXTURE_DIR = BACKEND_ROOT / "app" / "data" / "fixtures" / "benchmark_cases"
STRUCTURE_EXTENSIONS = {".pdb", ".ent", ".cif"}
MAPPING_EXTENSIONS = {".json", ".xml", ".tsv"}
ANNOTATION_EXTENSIONS = {".json", ".jsonl", ".csv", ".tsv", ".txt"}
DEPLOY_IMPORT_CONFIRMATION = "RUN_DEPLOY_DATA_IMPORT"
DATA_STATS_CACHE_TTL_SECONDS = 60
_data_stats_cache: tuple[float, dict[str, Any]] | None = None


class DeployDataImportRequest(BaseModel):
    annotations: str | None = None
    sifts: str | None = None
    pdb: str | None = None
    alphafold: str | None = None
    foldseek_root: str | None = None
    foldseek_pdb: str | None = None
    foldseek_alphafold: str | None = None
    foldseek_custom: str | None = None
    smoke_pdb: str | None = None
    symlink: bool = True
    dry_run: bool = True
    confirmation: str | None = None


class LipaseCurationCreateRequest(BaseModel):
    source_type: str
    paper_key: str | None = None
    title: str | None = None
    doi: str | None = None
    pmid: str | None = None
    enzyme_name: str | None = None
    mutation_code: str | None = None
    position: int | None = None
    linked_task_id: str | None = None
    evidence_payload: dict[str, Any] | None = None
    feedback_payload: dict[str, Any] | None = None
    notes: str | None = None


def _read_json_asset(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _component_count(readiness: dict[str, Any], name: str) -> int:
    component = (readiness.get("components") or {}).get(name)
    if not isinstance(component, dict):
        return 0
    try:
        return int(component.get("count") or 0)
    except (TypeError, ValueError):
        return 0


def _deploy_data_asset_counts(readiness: dict[str, Any], lipase_status: dict[str, Any]) -> dict[str, int]:
    root_info = readiness.get("root") if isinstance(readiness.get("root"), dict) else {}
    root = Path(str(root_info.get("path") or PROJECT_ROOT / "deploy_data"))
    annotations = root / "annotations"

    base_rows = _as_list(_read_json_asset(annotations / "base.json"))
    interpro_rows = _as_list(_read_json_asset(annotations / "interpro.json"))
    mcsa_rows = _as_list(_read_json_asset(annotations / "mcsa.json"))
    signalp_rows = _as_list(_read_json_asset(annotations / "signalp.json"))

    enzyme_ids: set[str] = set()
    taxonomy_ids: set[str] = set()
    ec_numbers: set[str] = set()
    pfam_ids: set[str] = set()
    for row in base_rows:
        if not isinstance(row, dict):
            continue
        enzyme = row.get("enzyme") if isinstance(row.get("enzyme"), dict) else {}
        uniprot_id = enzyme.get("uniprot_id") or row.get("uniprot_id")
        if uniprot_id:
            enzyme_ids.add(str(uniprot_id))
        taxonomy = row.get("taxonomy") if isinstance(row.get("taxonomy"), dict) else {}
        taxid = taxonomy.get("ncbi_taxid") or taxonomy.get("taxid")
        if taxid:
            taxonomy_ids.add(str(taxid))
        for ec in _as_list(row.get("ec_numbers")):
            if isinstance(ec, dict) and ec.get("ec_number"):
                ec_numbers.add(str(ec["ec_number"]))
        for pfam in _as_list(row.get("pfam_domains")):
            if isinstance(pfam, dict) and pfam.get("pfam_id"):
                pfam_ids.add(str(pfam["pfam_id"]))

    reaction_texts: set[str] = set()
    catalytic_residue_count = 0
    for row in mcsa_rows:
        if not isinstance(row, dict):
            continue
        if row.get("reaction_text"):
            reaction_texts.add(str(row["reaction_text"]))
        catalytic_residue_count += len(_as_list(row.get("residues")))

    lipase_summary = lipase_status.get("summary") if isinstance(lipase_status.get("summary"), dict) else {}
    return {
        "enzyme_records": len(enzyme_ids),
        "taxonomy": len(taxonomy_ids),
        "ec_numbers": len(ec_numbers),
        "pdb_structures": _component_count(readiness, "pdb"),
        "alphafold_structures": _component_count(readiness, "alphafold"),
        "kinetic_parameters": int(lipase_summary.get("metric_count") or 0),
        "stability_records": int(lipase_summary.get("claim_count") or 0),
        "substrate_compounds": int(lipase_summary.get("substrate_count") or 0),
        "reaction_equations": len(reaction_texts),
        "directed_evolution_entries": int(lipase_summary.get("variant_count") or 0),
        "pfam_domains": len(pfam_ids),
        "domain_architecture": len(pfam_ids),
        "interpro_entries": len(interpro_rows),
        "enzyme_interpro_links": len(interpro_rows),
        "catalytic_sites": len(mcsa_rows),
        "catalytic_residues": catalytic_residue_count,
        "signal_peptide_predictions": len(signalp_rows),
        "database_crossrefs": _component_count(readiness, "sifts"),
    }


class LipaseCurationReviewRequest(BaseModel):
    status: str
    reviewer_notes: str | None = None


class LipaseCurationBatchRequest(BaseModel):
    record_ids: list[int] | None = None
    source_type: str | None = None
    limit: int = 100
    dry_run: bool = True


class LipaseCurationBatchPublishRequest(BaseModel):
    confirmation: str
    reviewer_notes: str | None = None


class EnzymePolicyDecisionPublishRequest(BaseModel):
    dry_run: bool = True
    confirmation: str | None = None
    limit: int = 100


class EnzymeMetadataPolicyMaterializeRequest(BaseModel):
    dry_run: bool = True
    limit: int = 100


class EnzymeMetadataCurationReviewRequest(BaseModel):
    status: str
    reviewer_notes: str | None = None


class EnzymeMetadataCurationBatchRequest(BaseModel):
    record_ids: list[int] | None = None
    family: str | None = None
    record_type: str | None = None
    limit: int = 100
    dry_run: bool = True


class EnzymeMetadataCurationBatchArchiveRequest(BaseModel):
    confirmation: str
    reviewer_notes: str | None = None


class ExperimentFeedbackCreateRequest(BaseModel):
    project_id: str | None = None
    linked_task_id: str | None = None
    enzyme_name: str | None = None
    variant_name: str
    parent_variant: str | None = None
    mutations: list[str] | None = None
    assay_payload: dict[str, Any] | None = None
    metrics_payload: dict[str, Any] | None = None
    quality_payload: dict[str, Any] | None = None
    interpretation_payload: dict[str, Any] | None = None
    notes: str | None = None


class ExperimentFeedbackIterationPlanRequest(BaseModel):
    project_id: str | None = None
    enzyme_name: str | None = None
    objective: str = "multi_objective"
    mechanism_tags: dict[str, list[str]] | None = None
    structural_distances: dict[str, float] | None = None
    residue_distance_graph: dict[str, Any] | None = None
    same_region_groups: list[list[str]] | None = None
    remote_candidates: list[dict[str, Any]] | None = None
    allow_exploratory_combinations: bool = False


class WetLabCalibrationRunRequest(BaseModel):
    project_id: str | None = None
    enzyme_name: str | None = None
    objective: str = "multi_objective"
    assay_key: str | None = None
    include_all_users: bool = False


async def _require_feedback_project_access(
    session: AsyncSession,
    *,
    project_id: str | None,
    user: dict,
    write: bool = False,
) -> None:
    if not project_id:
        return
    project, access_role = await get_project_access(session, project_id=project_id, user_id=user["id"])
    action = "project.sequence.create" if write else "project.read"
    if not project or not can_perform_project_action(access_role, action):
        raise HTTPException(status_code=404, detail="Project not found")


def _expand_relative_path(relative_path: str) -> dict[str, Any]:
    candidate = PROJECT_ROOT / relative_path
    return {
        "relative_path": relative_path,
        "absolute_path": str(candidate),
        "exists": candidate.exists(),
    }


def _file_matches(path: Path, extensions: set[str]) -> bool:
    suffixes = [part.lower() for part in path.suffixes]
    if not suffixes:
        return False
    if suffixes[-1] in extensions:
        return True
    return len(suffixes) >= 2 and suffixes[-1] == ".gz" and suffixes[-2] in extensions


def _collect_files(root: Path, extensions: set[str]) -> list[Path]:
    if not root.exists():
        return []
    return sorted(candidate for candidate in root.rglob("*") if candidate.is_file() and _file_matches(candidate, extensions))


def _foldseek_lookup_entries(kind: str) -> set[str]:
    lookup = PROJECT_ROOT / "deploy_data" / "foldseek" / kind / f"protein_ai_{kind}.lookup"
    if not lookup.exists():
        return set()
    entries: set[str] = set()
    for raw_line in lookup.read_text(encoding="utf-8").splitlines():
        parts = raw_line.split("\t")
        if len(parts) >= 2 and parts[1].strip():
            entries.add(parts[1].strip())
    return entries


def _runtime_status(case: dict[str, Any]) -> dict[str, Any]:
    paths = case.get("paths", {})
    deploy_structure_file = PROJECT_ROOT / str(paths.get("deploy_structure_file", ""))
    deploy_alphafold_dir = PROJECT_ROOT / str(paths.get("deploy_alphafold_dir", ""))
    deploy_sifts_dir = PROJECT_ROOT / str(paths.get("deploy_sifts_dir", ""))
    deploy_annotations_dir = PROJECT_ROOT / str(paths.get("deploy_annotations_dir", ""))
    incoming_reference_docs_dir = PROJECT_ROOT / str(paths.get("incoming_reference_docs_dir", ""))
    incoming_reference_doc_manifest_file = PROJECT_ROOT / str(paths.get("incoming_reference_doc_manifest_file", ""))
    deploy_bundle_dir = PROJECT_ROOT / str(paths.get("deploy_bundle_dir", ""))
    deploy_bundle_manifest_file = PROJECT_ROOT / str(paths.get("deploy_bundle_manifest_file", ""))
    deploy_bundle_archive_file = PROJECT_ROOT / str(paths.get("deploy_bundle_archive_file", ""))
    discovery_report_file = PROJECT_ROOT / str(paths.get("discovery_report_file", ""))

    alphafold_files = _collect_files(deploy_alphafold_dir, STRUCTURE_EXTENSIONS)
    sifts_files = _collect_files(deploy_sifts_dir, MAPPING_EXTENSIONS)
    annotation_files = _collect_files(deploy_annotations_dir, ANNOTATION_EXTENSIONS)
    incoming_reference_docs = _collect_files(incoming_reference_docs_dir, {".pdf", ".doc", ".docx", ".md", ".txt"})

    pdb_lookup = _foldseek_lookup_entries("pdb")
    alphafold_lookup = _foldseek_lookup_entries("alphafold")
    structure_stem = deploy_structure_file.stem if deploy_structure_file.name else ""
    discovery_counts: dict[str, int] = {}
    if discovery_report_file.exists():
        try:
            payload = json.loads(discovery_report_file.read_text(encoding="utf-8"))
            counts = payload.get("counts", {})
            if isinstance(counts, dict):
                discovery_counts = {str(key): int(value) for key, value in counts.items()}
        except (OSError, ValueError, TypeError):
            discovery_counts = {}

    return {
        "pdb_staged": deploy_structure_file.exists(),
        "alphafold_ready": bool(alphafold_files),
        "sifts_ready": bool(sifts_files),
        "annotations_ready": bool(annotation_files),
        "foldseek_indexed": bool(structure_stem and structure_stem in pdb_lookup),
        "bundle_ready": deploy_bundle_dir.exists() and deploy_bundle_manifest_file.exists(),
        "bundle_archive_ready": deploy_bundle_archive_file.exists(),
        "reference_docs_ready": bool(incoming_reference_docs),
        "reference_doc_manifest_ready": incoming_reference_doc_manifest_file.exists(),
        "discovery_report_ready": discovery_report_file.exists(),
        "asset_counts": {
            "alphafold_structures": len(alphafold_files),
            "sifts_mappings": len(sifts_files),
            "annotation_files": len(annotation_files),
            "reference_doc_files": len(incoming_reference_docs),
            "foldseek_pdb_entries": 1 if structure_stem and structure_stem in pdb_lookup else 0,
            "foldseek_alphafold_entries": len(alphafold_lookup),
            "bundle_files": len(_collect_files(deploy_bundle_dir, STRUCTURE_EXTENSIONS | MAPPING_EXTENSIONS | ANNOTATION_EXTENSIONS | {".md"})),
            "bundle_archive_size_bytes": deploy_bundle_archive_file.stat().st_size if deploy_bundle_archive_file.exists() else 0,
            "discovered_structures": int(discovery_counts.get("structures", 0)),
            "discovered_alphafold": int(discovery_counts.get("alphafold", 0)),
            "discovered_sifts": int(discovery_counts.get("sifts", 0)),
            "discovered_annotations": int(discovery_counts.get("annotations", 0)),
            "discovered_reference_docs": int(discovery_counts.get("reference_docs", 0)),
        },
    }


def _discovery_preview(case: dict[str, Any], limit: int = 5) -> dict[str, Any] | None:
    paths = case.get("paths", {})
    discovery_report_file = PROJECT_ROOT / str(paths.get("discovery_report_file", ""))
    if not discovery_report_file.exists():
        return None
    try:
        payload = json.loads(discovery_report_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None

    counts = payload.get("counts", {})
    results = payload.get("results", {})
    if not isinstance(counts, dict) or not isinstance(results, dict):
        return None

    preview: dict[str, list[dict[str, Any]]] = {}
    for category, items in results.items():
        if not isinstance(items, list):
            continue
        preview[str(category)] = [
            {
                "path": str(item.get("path", "")),
                "project_relative_path": str(item.get("project_relative_path", "")),
                "size_bytes": int(item.get("size_bytes", 0) or 0),
                "score": int(item.get("score", 0) or 0),
            }
            for item in items[:limit]
            if isinstance(item, dict)
        ]

    return {
        "report_path": _expand_relative_path(str(paths.get("discovery_report_file", ""))),
        "counts": {str(key): int(value or 0) for key, value in counts.items()},
        "preview": preview,
    }


def _selected_reference_docs(case: dict[str, Any], limit: int = 10) -> dict[str, Any] | None:
    paths = case.get("paths", {})
    manifest_file = PROJECT_ROOT / str(paths.get("incoming_reference_doc_manifest_file", ""))
    if not manifest_file.exists():
        return None
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    selected = payload.get("selected", [])
    if not isinstance(selected, list):
        return None
    preview = []
    for item in selected[:limit]:
        if not isinstance(item, dict):
            continue
        preview.append(
            {
                "source_path": str(item.get("source_path", "")),
                "staged_path": str(item.get("staged_path", "")),
                "score": int(item.get("score", 0) or 0),
                "size_bytes": int(item.get("size_bytes", 0) or 0),
            }
        )
    return {
        "manifest_path": _expand_relative_path(str(paths.get("incoming_reference_doc_manifest_file", ""))),
        "selected_count": int(payload.get("selected_count", len(preview)) or 0),
        "preview": preview,
    }


def _benchmark_maturity(status: dict[str, Any]) -> str:
    if bool(status.get("bundle_archive_ready")):
        return "delivery-ready"
    if bool(status.get("bundle_ready")):
        return "bundle-ready"
    if bool(status.get("foldseek_indexed")):
        return "structure-ready"
    if bool(status.get("pdb_staged")):
        return "staged"
    return "seed-only"


def _bundle_summary(case: dict[str, Any]) -> dict[str, Any] | None:
    paths = case.get("paths", {})
    bundle_manifest_file = PROJECT_ROOT / str(paths.get("deploy_bundle_manifest_file", ""))
    bundle_archive_file = PROJECT_ROOT / str(paths.get("deploy_bundle_archive_file", ""))
    if not bundle_manifest_file.exists():
        return None
    try:
        payload = json.loads(bundle_manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    bundle_contents = payload.get("bundle_contents", {})
    if not isinstance(bundle_contents, dict):
        bundle_contents = {}
    case_id = str(case.get("id", "")).strip()
    return {
        "manifest_path": _expand_relative_path(str(paths.get("deploy_bundle_manifest_file", ""))),
        "archive_path": _expand_relative_path(str(paths.get("deploy_bundle_archive_file", ""))),
        "download_url": f"/api/data/benchmarks/{case_id}/bundle/download" if case_id else None,
        "archive_size_bytes": bundle_archive_file.stat().st_size if bundle_archive_file.exists() else 0,
        "bundle_contents": {str(key): int(value or 0) for key, value in bundle_contents.items()},
    }


@lru_cache(maxsize=1)
def _load_benchmark_cases() -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    if not BENCHMARK_FIXTURE_DIR.exists():
        return cases

    for candidate in sorted(BENCHMARK_FIXTURE_DIR.glob("*.json")):
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        case_id = str(payload.get("id") or candidate.stem)
        payload["id"] = case_id
        payload.setdefault("slug", case_id)
        cases[case_id] = payload
    return cases


def _benchmark_summary(case: dict[str, Any]) -> dict[str, Any]:
    paths = case.get("paths", {})
    source_ready = bool(paths.get("source_bundle_dir")) and (PROJECT_ROOT / paths["source_bundle_dir"]).exists()
    deploy_structure_ready = bool(paths.get("deploy_structure_file")) and (PROJECT_ROOT / paths["deploy_structure_file"]).exists()
    status = _runtime_status(case)
    mutations = case.get("candidate_mutations", [])
    return {
        "id": case["id"],
        "slug": case.get("slug", case["id"]),
        "title": case.get("title", case["id"]),
        "program": case.get("program"),
        "protein_name": case.get("protein_name"),
        "objective": case.get("objective"),
        "target_ph_range": case.get("target_ph_range", {}),
        "sequence_length": case.get("sequence_length"),
        "candidate_mutation_count": len(mutations),
        "maturity": _benchmark_maturity(status),
        "bundle_download_url": f"/api/data/benchmarks/{case['id']}/bundle/download",
        "asset_status": {
            "source_bundle_ready": source_ready,
            "deploy_structure_ready": deploy_structure_ready,
            "foldseek_indexed": bool(status.get("foldseek_indexed")),
            "alphafold_ready": bool(status.get("alphafold_ready")),
            "sifts_ready": bool(status.get("sifts_ready")),
            "annotations_ready": bool(status.get("annotations_ready")),
            "bundle_ready": bool(status.get("bundle_ready")),
            "bundle_archive_ready": bool(status.get("bundle_archive_ready")),
            "reference_docs_ready": bool(status.get("reference_docs_ready")),
            "reference_doc_manifest_ready": bool(status.get("reference_doc_manifest_ready")),
            "discovery_report_ready": bool(status.get("discovery_report_ready")),
        },
        "asset_counts": status.get("asset_counts", {}),
    }


def _benchmark_detail(case: dict[str, Any]) -> dict[str, Any]:
    detail = dict(case)
    raw_paths = case.get("paths", {})
    detail["paths"] = {
        key: _expand_relative_path(value)
        for key, value in raw_paths.items()
    }
    detail["status"] = _runtime_status(case)
    detail["discovery"] = _discovery_preview(case)
    detail["selected_reference_docs"] = _selected_reference_docs(case)
    detail["bundle"] = _bundle_summary(case)
    detail["summary"] = _benchmark_summary(case)
    return detail


# =============================================================================
# Benchmarks
# =============================================================================
@router.get("/benchmarks")
async def list_benchmarks():
    """List real benchmark cases bundled with the platform."""
    cases = _load_benchmark_cases()
    return {
        "benchmarks": [_benchmark_summary(case) for case in cases.values()],
        "count": len(cases),
    }


@router.get("/benchmarks/{case_id}")
async def get_benchmark_case(case_id: str):
    """Return one benchmark case with runtime path checks."""
    case = _load_benchmark_cases().get(case_id)
    if case is None:
        raise HTTPException(404, f"Benchmark case {case_id} not found")
    return _benchmark_detail(case)


@router.head("/benchmarks/{case_id}/bundle/download")
@router.get("/benchmarks/{case_id}/bundle/download")
async def download_benchmark_bundle(case_id: str):
    """Download one benchmark bundle archive."""
    case = _load_benchmark_cases().get(case_id)
    if case is None:
        raise HTTPException(404, f"Benchmark case {case_id} not found")
    paths = case.get("paths", {})
    archive_file = PROJECT_ROOT / str(paths.get("deploy_bundle_archive_file", ""))
    if not archive_file.exists() or not archive_file.is_file():
        raise HTTPException(404, f"Benchmark bundle archive for {case_id} not found")
    return FileResponse(
        path=archive_file,
        media_type="application/gzip",
        filename=archive_file.name,
    )


# =============================================================================
# Search
# =============================================================================
@router.get("/search")
async def search_data(
    q: str = Query(..., min_length=2, description="Search query"),
    category: str | None = Query(None, description="Filter: protein, substrate, reaction, ec"),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Cross-database search: protein name, EC number, substrate, reaction."""
    results: dict[str, list[dict]] = {}

    if not category or category == "protein":
        query = (
            select(EnzymeRecord.uniprot_id, EnzymeRecord.protein_name, EnzymeRecord.gene_name, EnzymeRecord.description)
            .where(
                (EnzymeRecord.protein_name.ilike(f"%{q}%"))
                | (EnzymeRecord.gene_name.ilike(f"%{q}%"))
                | (EnzymeRecord.uniprot_id.ilike(f"%{q}%"))
                | (EnzymeRecord.description.ilike(f"%{q}%"))
            )
            .limit(limit)
        )
        rows = await session.execute(query)
        results["proteins"] = [
            {"uniprot_id": r[0], "name": r[1], "gene": r[2], "description": (r[3] or "")[:200]}
            for r in rows.fetchall()
        ]

    if not category or category == "substrate":
        query = select(SubstrateCompound).where(
            SubstrateCompound.name.ilike(f"%{q}%")
            | (SubstrateCompound.iupac_name.ilike(f"%{q}%"))
        ).limit(limit)
        rows = await session.execute(query)
        results["substrates"] = [
            {"cid": s.pubchem_cid, "name": s.name, "formula": s.molecular_formula, "smiles": s.smiles}
            for s in rows.scalars()
        ]

    if not category or category == "reaction":
        query = select(ReactionEquation.rhea_id, ReactionEquation.equation).where(
            ReactionEquation.equation.ilike(f"%{q}%")
        ).limit(limit)
        rows = await session.execute(query)
        results["reactions"] = [{"rhea_id": r[0], "equation": r[1]} for r in rows.fetchall()]

    if not category or category == "ec":
        query = select(ECNumber.ec_number, ECNumber.name).where(
            ECNumber.ec_number.like(f"%{q}%") | (ECNumber.name.ilike(f"%{q}%"))
        ).limit(limit)
        rows = await session.execute(query)
        results["ec_numbers"] = [{"ec": r[0], "name": r[1]} for r in rows.fetchall()]

    return {"query": q, "results": results}


# =============================================================================
# Protein detail (aggregated view)
# =============================================================================
@router.get("/protein/{uniprot_id}")
async def get_protein(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Aggregated protein detail: sequence, function, taxonomy, ECs, structures, etc."""
    service = AnnotationQueryService(session)
    payload = await service.get_protein_summary(uniprot_id)
    if payload is None:
        raise HTTPException(404, f"Protein {uniprot_id} not found")
    return payload


# =============================================================================
# Kinetics sub-resource
# =============================================================================
@router.get("/protein/{uniprot_id}/kinetics")
async def get_protein_kinetics(
    uniprot_id: str,
    param_type: str | None = Query(None, description="Filter: Kcat, Km, Ki, Kcat/Km"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Kinetic parameters (BRENDA/OED) for a protein."""
    service = AnnotationQueryService(session)
    enzyme = await service.get_enzyme(uniprot_id)
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    query = select(KineticParameter).where(KineticParameter.enzyme_id == enzyme.id)
    if param_type:
        query = query.where(KineticParameter.param_type == param_type)
    query = query.order_by(KineticParameter.param_type).limit(limit)

    rows = await session.execute(query)
    return {
        "uniprot_id": uniprot_id,
        "parameters": [
            {
                "type": kp.param_type,
                "substrate": kp.substrate_name,
                "value": kp.value,
                "unit": kp.unit,
                "ph": kp.ph,
                "temp_c": kp.temperature_c,
                "mutant": kp.mutant,
                "organism": kp.organism_name,
                "source": kp.source_db,
                "reference": kp.literature_ref,
            }
            for kp in rows.scalars()
        ],
    }


# =============================================================================
# Stability sub-resource
# =============================================================================
@router.get("/protein/{uniprot_id}/stability")
async def get_protein_stability(
    uniprot_id: str,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Stability records (ProThermDB) for a protein."""
    service = AnnotationQueryService(session)
    enzyme = await service.get_enzyme(uniprot_id)
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    rows = await session.execute(
        select(StabilityRecord)
        .where(StabilityRecord.enzyme_id == enzyme.id)
        .order_by(StabilityRecord.mutation_pos)
        .limit(limit)
    )
    return {
        "uniprot_id": uniprot_id,
        "records": [
            {
                "mutation": s.mutation,
                "position": s.mutation_pos,
                "wt": s.wild_type,
                "mt": s.mutant,
                "ddg": s.ddg,
                "dtm": s.dtm,
                "ph": s.ph,
                "temp_c": s.temperature_c,
                "method": s.method,
                "reference": s.literature_ref,
            }
            for s in rows.scalars()
        ],
    }


# =============================================================================
# Structures sub-resource
# =============================================================================
@router.get("/protein/{uniprot_id}/structures")
async def get_protein_structures(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """PDB and AlphaFold structures for a protein."""
    service = AnnotationQueryService(session)
    enzyme = await service.get_enzyme(uniprot_id)
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    pdb_rows = await session.execute(
        select(PDBStructure).where(PDBStructure.enzyme_id == enzyme.id)
    )
    af_rows = await session.execute(
        select(AlphaFoldStructure).where(AlphaFoldStructure.enzyme_id == enzyme.id)
    )

    return {
        "uniprot_id": uniprot_id,
        "pdb": [
            {"pdb_id": s.pdb_id, "title": s.title, "method": s.method, "resolution": s.resolution,
             "chains": s.chain_ids, "deposited": s.deposited_at.isoformat() if s.deposited_at else None}
            for s in pdb_rows.scalars()
        ],
        "alphafold": [
            {"plddt_mean": s.plddt_mean, "model_url": s.model_url}
            for s in af_rows.scalars()
        ],
    }


# =============================================================================
# Evolution sub-resource
# =============================================================================
@router.get("/protein/{uniprot_id}/evolution")
async def get_protein_evolution(
    uniprot_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Directed evolution entries (EnzEngDB) for a protein."""
    service = AnnotationQueryService(session)
    enzyme = await service.get_enzyme(uniprot_id)
    if not enzyme:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    rows = await session.execute(
        select(DirectedEvolutionEntry)
        .where(DirectedEvolutionEntry.enzyme_id == enzyme.id)
        .order_by(DirectedEvolutionEntry.fold_improvement.desc().nullslast())
        .limit(limit)
    )
    return {
        "uniprot_id": uniprot_id,
        "experiments": [
            {
                "name": e.experiment_name,
                "method": e.mutagenesis_method,
                "selection": e.selection_pressure,
                "library_size": e.library_size,
                "rounds": e.rounds,
                "best_variant": e.best_variant,
                "mutations": e.mutations_introduced,
                "fold_improvement": e.fold_improvement,
                "metric": e.improvement_metric,
                "reference": e.literature_ref,
            }
            for e in rows.scalars()
        ],
    }


# =============================================================================
# Annotation sub-resources
# =============================================================================
@router.get("/protein/{uniprot_id}/annotations")
async def get_protein_annotations(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """InterPro/Pfam annotation bundle for a protein."""
    service = AnnotationQueryService(session)
    enzyme = await service.get_enzyme_with_annotations(uniprot_id)
    if enzyme is None:
        raise HTTPException(404, f"Protein {uniprot_id} not found")
    return service.build_annotations_payload(enzyme)


@router.get("/protein/{uniprot_id}/catalytic-sites")
async def get_protein_catalytic_sites(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Curated catalytic site bundle for a protein."""
    service = AnnotationQueryService(session)
    enzyme = await service.get_enzyme_with_annotations(uniprot_id)
    if enzyme is None:
        raise HTTPException(404, f"Protein {uniprot_id} not found")
    return service.build_catalytic_sites_payload(enzyme)


@router.get("/protein/{uniprot_id}/signal-peptide")
async def get_protein_signal_peptide(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Latest signal peptide prediction for a protein."""
    service = AnnotationQueryService(session)
    enzyme = await service.get_enzyme_with_annotations(uniprot_id)
    if enzyme is None:
        raise HTTPException(404, f"Protein {uniprot_id} not found")
    payload = service.build_signal_peptide_payload(enzyme)
    if payload is None:
        raise HTTPException(404, f"Signal peptide prediction for {uniprot_id} not found")
    return payload


@router.get("/protein/{uniprot_id}/annotation-bundle")
async def get_protein_annotation_bundle(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Aggregated annotation bundle for one protein."""
    service = AnnotationQueryService(session)
    enzyme = await service.get_enzyme(uniprot_id)
    if enzyme is None:
        raise HTTPException(404, f"Protein {uniprot_id} not found")

    from app.services.annotation_facade import AnnotationFacade

    facade = AnnotationFacade(session)
    return await facade.resolve_annotation_bundle(uniprot_id=uniprot_id)


@router.get("/protein/{uniprot_id}/reaction-profile")
async def get_protein_reaction_profile(
    uniprot_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Read-only local reaction profile using exact EC-to-Rhea matches only."""
    payload = await ReactionProfileService(session).resolve(uniprot_id)
    if payload is None:
        raise HTTPException(404, f"Protein {uniprot_id} not found")
    return payload


# =============================================================================
# EC number lookup
# =============================================================================
@router.get("/ec/{ec_number:path}")
async def get_ec_number(
    ec_number: str,
    session: AsyncSession = Depends(get_session),
):
    """Look up an EC number and its linked proteins."""
    row = await session.execute(
        select(ECNumber).where(ECNumber.ec_number == ec_number)
    )
    ec = row.scalar()
    if not ec:
        raise HTTPException(404, f"EC {ec_number} not found")

    # Get linked proteins
    link_rows = await session.execute(
        select(EnzymeECLink, EnzymeRecord)
        .join(EnzymeRecord, EnzymeECLink.enzyme_id == EnzymeRecord.id)
        .where(EnzymeECLink.ec_id == ec.id)
        .limit(50)
    )
    proteins = [
        {"uniprot_id": r[1].uniprot_id, "name": r[1].protein_name, "primary": r[0].is_primary}
        for r in link_rows.fetchall()
    ]

    return {
        "ec_number": ec.ec_number,
        "name": ec.name,
        "category": ec.category,
        "proteins": proteins,
        "protein_count": len(proteins),
    }


# =============================================================================
# Substrate lookup
# =============================================================================
@router.get("/substrate/{query}")
async def get_substrate(
    query: str,
    session: AsyncSession = Depends(get_session),
):
    """Search for a substrate compound by name or PubChem CID."""
    # Try exact CID match first
    try:
        cid = int(query)
        row = await session.execute(select(SubstrateCompound).where(SubstrateCompound.pubchem_cid == cid))
        compound = row.scalar()
        if compound:
            return _compound_dict(compound)
    except ValueError:
        pass

    # Fuzzy name search
    rows = await session.execute(
        select(SubstrateCompound)
        .where(
            SubstrateCompound.name.ilike(f"%{query}%")
            | SubstrateCompound.inchikey.ilike(f"%{query}%")
        )
        .limit(10)
    )
    compounds = [_compound_dict(c) for c in rows.scalars()]
    return {"query": query, "results": compounds}


# =============================================================================
# Reaction lookup
# =============================================================================
@router.get("/reaction/{rhea_id}")
async def get_reaction(
    rhea_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Look up a Rhea reaction by ID."""
    row = await session.execute(
        select(ReactionEquation).where(ReactionEquation.rhea_id == rhea_id)
    )
    rxn = row.scalar()
    if not rxn:
        raise HTTPException(404, f"Rhea reaction {rhea_id} not found")

    return {
        "rhea_id": rxn.rhea_id,
        "equation": rxn.equation,
        "reaction_side": rxn.reaction_side,
        "reactants": rxn.reactants,
        "products": rxn.products,
        "cofactors": rxn.cofactors,
        "ec_numbers": rxn.ec_numbers,
        "is_balanced": rxn.is_balanced,
        "is_transport": rxn.is_transport,
    }


# =============================================================================
# Statistics
# =============================================================================
@router.get("/readiness")
async def get_data_readiness():
    """Read-only readiness status for local deploy_data assets."""
    return collect_deploy_data_readiness()


@router.get("/tool-capabilities")
async def get_tool_capabilities():
    """Return report-facing capability labels and scientific boundaries."""
    return tool_capability_audit()


@router.get("/lipase/status")
async def get_lipase_db_status():
    """Read-only status and quality snapshot for the KWB lipase evidence DB."""
    return collect_lipase_db_status()


@router.get("/lipase/search")
async def search_lipase_db(
    q: str = Query(..., min_length=1, description="Lipase evidence search query"),
    limit: int = Query(default=50, ge=1, le=100),
    include_non_ready: bool = Query(default=False, description="Include hold/non-ready rows for curator audit only"),
):
    """Search KWB lipase papers, variants, claims, substrates, and curation gaps."""
    return search_lipase_evidence(q=q, limit=limit, include_non_ready=include_non_ready)


@router.get("/lipase/evidence-context")
async def get_lipase_evidence_context(
    mutations: list[str] | None = Query(default=None, description="Mutation labels such as D223G; repeat query param for multiple values"),
    positions: list[int] | None = Query(default=None, description="1-indexed mutation positions; repeat query param for multiple values"),
    q: str | None = Query(default=None, description="Optional fallback search query"),
    limit: int = Query(default=20, ge=1, le=100),
    include_non_ready: bool = Query(default=False, description="Include hold/non-ready rows for curator audit only"),
):
    """Return compact lipase evidence context for mutation, structure, and MD ranking tools."""
    return build_lipase_evidence_context(
        mutations=mutations,
        positions=positions,
        q=q,
        limit=limit,
        include_non_ready=include_non_ready,
    )


@router.post("/experiment-feedback")
async def submit_experiment_feedback(
    req: ExperimentFeedbackCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Submit wet-lab phenotype feedback for a WT, single mutant, or combination variant."""
    await _require_feedback_project_access(
        session,
        project_id=req.project_id,
        user=current_user,
        write=True,
    )
    try:
        record = await create_experiment_feedback_record(
            session,
            user_id=current_user["id"],
            payload=req.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "recorded", "record": record}


@router.get("/experiment-feedback")
async def list_experiment_feedback(
    project_id: str | None = Query(default=None),
    enzyme_name: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    include_all_users: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """List current user's wet-lab feedback records, optionally scoped to a readable project."""
    await _require_feedback_project_access(
        session,
        project_id=project_id,
        user=current_user,
        write=False,
    )
    records = await list_experiment_feedback_records(
        session,
        user_id=current_user["id"],
        project_id=project_id,
        enzyme_name=enzyme_name,
        decision=decision,
        include_all_users=include_all_users and current_user.get("role") == "admin",
        limit=limit,
    )
    return {"count": len(records), "records": records}


@router.get("/experiment-feedback/summary")
async def summarize_experiment_feedback(
    project_id: str | None = Query(default=None),
    enzyme_name: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    include_all_users: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Summarize wet-lab feedback into Go/Watch/No-Go counts and combination readiness."""
    await _require_feedback_project_access(
        session,
        project_id=project_id,
        user=current_user,
        write=False,
    )
    records = await list_experiment_feedback_records(
        session,
        user_id=current_user["id"],
        project_id=project_id,
        enzyme_name=enzyme_name,
        decision=decision,
        include_all_users=include_all_users and current_user.get("role") == "admin",
        limit=limit,
    )
    return summarize_feedback_records(records)


@router.get("/experiment-feedback/calibration-preview")
async def preview_wet_lab_calibration(
    project_id: str | None = Query(default=None),
    enzyme_name: str | None = Query(default=None),
    objective: str = Query(default="multi_objective"),
    assay_key: str | None = Query(default=None),
    include_all_users: bool = Query(default=False),
    limit: int = Query(default=1000, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Preview wet-lab calibration status without writing a calibration run."""
    await _require_feedback_project_access(
        session,
        project_id=project_id,
        user=current_user,
        write=False,
    )
    records = await list_experiment_feedback_records(
        session,
        user_id=current_user["id"],
        project_id=project_id,
        enzyme_name=enzyme_name,
        include_all_users=include_all_users and current_user.get("role") == "admin",
        limit=limit,
    )
    return build_calibration_summary(records, objective=objective, assay_key=assay_key)


@router.post("/experiment-feedback/calibration-runs")
async def create_wet_lab_calibration(
    req: WetLabCalibrationRunRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Materialize a conservative calibration summary from recorded wet-lab feedback."""
    await _require_feedback_project_access(
        session,
        project_id=req.project_id,
        user=current_user,
        write=False,
    )
    return {
        "status": "recorded",
        "calibration": await create_wet_lab_calibration_run(
            session,
            user_id=current_user["id"],
            project_id=req.project_id,
            enzyme_name=req.enzyme_name,
            objective=req.objective,
            assay_key=req.assay_key,
            include_all_users=req.include_all_users and current_user.get("role") == "admin",
        ),
    }


@router.get("/experiment-feedback/calibration-runs")
async def list_wet_lab_calibrations(
    project_id: str | None = Query(default=None),
    enzyme_name: str | None = Query(default=None),
    objective: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """List materialized wet-lab calibration summaries for the current user."""
    await _require_feedback_project_access(
        session,
        project_id=project_id,
        user=current_user,
        write=False,
    )
    return {
        "records": await list_wet_lab_calibration_runs(
            session,
            user_id=current_user["id"],
            project_id=project_id,
            enzyme_name=enzyme_name,
            objective=objective,
            limit=limit,
        )
    }


@router.post("/experiment-feedback/iteration-plan")
async def plan_experiment_feedback_iteration(
    req: ExperimentFeedbackIterationPlanRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Build a conservative second-round plan from the user's stored wet-lab feedback."""
    await _require_feedback_project_access(
        session,
        project_id=req.project_id,
        user=current_user,
        write=False,
    )
    records = await list_experiment_feedback_records(
        session,
        user_id=current_user["id"],
        project_id=req.project_id,
        enzyme_name=req.enzyme_name,
        limit=500,
    )
    return await feedback_iteration_planner(
        records,
        objective=req.objective,
        mechanism_tags=req.mechanism_tags,
        structural_distances=req.structural_distances,
        residue_distance_graph=req.residue_distance_graph,
        same_region_groups=req.same_region_groups,
        remote_candidates=req.remote_candidates,
        allow_exploratory_combinations=req.allow_exploratory_combinations,
    )


@router.post("/lipase/curation-records")
async def submit_lipase_curation_record(
    req: LipaseCurationCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Submit a platform-side enrichment candidate without modifying the read-only lipase DB."""
    try:
        record = await create_lipase_curation_record(session, user_id=current_user["id"], payload=req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "submitted", "record": record}


@router.get("/lipase/curation-records")
async def list_lipase_curation_queue(
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """List submitted lipase enrichment candidates for administrator review."""
    try:
        records = await list_lipase_curation_records(session, status=status, source_type=source_type, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"count": len(records), "records": records, "reviewer_user_id": current_user["id"]}


@router.patch("/lipase/curation-records/{record_id}/review")
async def review_lipase_curation_record(
    record_id: int,
    req: LipaseCurationReviewRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """Update manual review status for a lipase curation candidate."""
    try:
        record = await update_lipase_curation_review(
            session,
            record_id=record_id,
            reviewer_user_id=current_user["id"],
            status=req.status,
            reviewer_notes=req.reviewer_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Lipase curation record not found")
    return {"status": "updated", "record": record}


@router.post("/lipase/curation-batches")
async def create_lipase_curation_import_batch(
    req: LipaseCurationBatchRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """Create or preview a controlled manual-import batch from accepted curation records."""
    try:
        if req.dry_run:
            preview = await preview_lipase_curation_batch(
                session,
                record_ids=req.record_ids,
                source_type=req.source_type,
                limit=req.limit,
            )
            return preview
        batch = await create_lipase_curation_batch(
            session,
            user_id=current_user["id"],
            record_ids=req.record_ids,
            source_type=req.source_type,
            limit=req.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "prepared", "batch": batch}


@router.get("/lipase/curation-batches")
async def list_lipase_curation_import_batches(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """List controlled lipase curation import batches for administrator review."""
    try:
        batches = await list_lipase_curation_batches(session, status=status, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"count": len(batches), "batches": batches, "reviewer_user_id": current_user["id"]}


@router.patch("/lipase/curation-batches/{batch_id}/publish")
async def publish_lipase_curation_import_batch(
    batch_id: int,
    req: LipaseCurationBatchPublishRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """Mark a prepared curation batch as published after explicit manual confirmation."""
    try:
        batch = await publish_lipase_curation_batch(
            session,
            batch_id=batch_id,
            user_id=current_user["id"],
            confirmation=req.confirmation,
            reviewer_notes=req.reviewer_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if batch is None:
        raise HTTPException(status_code=404, detail="Lipase curation batch not found")
    return {"status": "published", "batch": batch}


@router.get("/lipase/papers")
async def get_lipase_papers(
    q: str | None = Query(default=None, description="Optional paper/enzyme/objective search query"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List curated lipase papers with aggregate evidence counts."""
    return list_lipase_papers(q=q, limit=limit)


@router.get("/lipase/papers/{paper_key}")
async def get_lipase_paper(paper_key: str):
    """Return one lipase paper with variants, claims, aliases, and curation gaps."""
    detail = get_lipase_paper_detail(paper_key)
    if detail is None:
        raise HTTPException(404, f"Lipase paper {paper_key} not found")
    return detail


@router.get("/lipase/variants")
async def get_lipase_variants(
    q: str | None = Query(default=None, description="Optional variant/paper/enzyme search query"),
    limit: int = Query(default=50, ge=1, le=200),
    include_non_ready: bool = Query(default=False, description="Include hold/non-ready rows for curator audit only"),
):
    """List lipase variants with linked paper, claim, and metric evidence."""
    return list_lipase_variants(q=q, limit=limit, include_non_ready=include_non_ready)


@router.get("/lipase/gaps")
async def get_lipase_gaps(
    priority: str | None = Query(default=None, description="Filter by gap priority"),
    status: str | None = Query(default=None, description="Filter by gap status"),
    limit: int = Query(default=100, ge=1, le=500),
):
    """List lipase evidence gaps for curation planning."""
    return list_lipase_gaps(priority=priority, status=status, limit=limit)


@router.get("/enzyme-dbs/status")
async def get_enzyme_dbs_status():
    """Read-only status for local simplified enzyme evidence databases."""
    return list_enzyme_db_families()


@router.get("/enzyme-dbs/{family}/status")
async def get_enzyme_db_family_status(family: str):
    """Read-only status for one simplified enzyme evidence database."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    return collect_simple_enzyme_db_status(family)


@router.get("/enzyme-dbs/{family}/papers")
async def get_enzyme_db_papers(
    family: str,
    q: str | None = Query(default=None, description="Optional paper/title/DOI/PMID search query"),
    limit: int = Query(default=50, ge=1, le=500),
):
    """List papers from one simplified enzyme evidence database."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    return list_simple_enzyme_papers(family, q=q, limit=limit)


@router.get("/enzyme-dbs/{family}/variants")
async def get_enzyme_db_variants(
    family: str,
    q: str | None = Query(default=None, description="Optional variant/mutation/effect search query"),
    limit: int = Query(default=50, ge=1, le=500),
):
    """List variants from one simplified enzyme evidence database."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    return list_simple_enzyme_variants(family, q=q, limit=limit)


@router.get("/enzyme-dbs/{family}/measurements")
async def get_enzyme_db_measurements(
    family: str,
    q: str | None = Query(default=None, description="Optional measurement/property/substrate search query"),
    limit: int = Query(default=50, ge=1, le=500),
):
    """List measurements from one simplified enzyme evidence database."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    return list_simple_enzyme_measurements(family, q=q, limit=limit)


@router.get("/enzyme-dbs/{family}/export-safe/measurements")
async def get_enzyme_db_export_safe_measurements(
    family: str,
    q: str | None = Query(default=None, description="Optional measurement/property/substrate search query"),
    limit: int = Query(default=500, ge=1, le=2000),
):
    """List A-only compact-schema measurements eligible for high-confidence export."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    return list_simple_enzyme_export_safe_measurements(family, q=q, limit=limit)


@router.post("/enzyme-dbs/{family}/policy-decisions/preview")
async def preview_enzyme_db_policy_decisions(
    family: str,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict = Depends(require_admin),
):
    """Preview sidecar patent/preprint policy decisions for manual curation."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    preview = preview_simple_enzyme_policy_decision_batch(family, limit=limit)
    return {**preview, "reviewer_user_id": current_user["id"]}


@router.post("/enzyme-dbs/{family}/policy-decisions/publish")
async def publish_enzyme_db_policy_decisions(
    family: str,
    req: EnzymePolicyDecisionPublishRequest,
    current_user: dict = Depends(require_admin),
):
    """Prepare the formal policy-decision release plan; real apply is currently blocked."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    limit = max(1, min(int(req.limit or 100), 500))
    if req.dry_run:
        preview = preview_simple_enzyme_policy_decision_batch(family, limit=limit)
        return {
            **preview,
            "publish_status": "planned",
            "sqlite_mutation_allowed": False,
            "export_safe": False,
            "reviewer_user_id": current_user["id"],
        }
    if req.confirmation != POLICY_DECISION_CONFIRMATION_TOKEN:
        raise HTTPException(
            status_code=422,
            detail=f"Set confirmation to {POLICY_DECISION_CONFIRMATION_TOKEN} to prepare a blocked publish plan",
        )
    try:
        blocked = publish_simple_enzyme_policy_decision_batch(
            family,
            confirmation=req.confirmation,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise HTTPException(
        status_code=409,
        detail={
            **blocked,
            "publish_status": "blocked",
            "sqlite_mutation_allowed": False,
            "export_safe": False,
            "reviewer_user_id": current_user["id"],
        },
    )


@router.post("/enzyme-dbs/{family}/metadata-curation/materialize")
async def materialize_enzyme_db_metadata_policy_decisions(
    family: str,
    req: EnzymeMetadataPolicyMaterializeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """Materialize sidecar policy decisions into the platform review queue only."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    try:
        result = await materialize_enzyme_metadata_policy_decisions(
            session,
            family=family,
            user_id=current_user["id"],
            limit=req.limit,
            dry_run=req.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**result, "reviewer_user_id": current_user["id"]}


@router.get("/enzyme-metadata/curation-records")
async def list_enzyme_metadata_curation_queue(
    family: str | None = Query(default=None),
    status: str | None = Query(default=None),
    record_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """List materialized simple-enzyme metadata curation records."""
    try:
        records = await list_enzyme_metadata_curation_records(
            session,
            family=family,
            status=status,
            record_type=record_type,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"count": len(records), "records": records, "reviewer_user_id": current_user["id"]}


@router.patch("/enzyme-metadata/curation-records/{record_id}/review")
async def review_enzyme_metadata_curation_record(
    record_id: int,
    req: EnzymeMetadataCurationReviewRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """Review a materialized metadata policy decision without modifying external SQLite DBs."""
    try:
        record = await update_enzyme_metadata_curation_review(
            session,
            record_id=record_id,
            reviewer_user_id=current_user["id"],
            status=req.status,
            reviewer_notes=req.reviewer_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Metadata curation record not found")
    return {"status": "updated", "record": record}


@router.post("/enzyme-metadata/curation-batches")
async def create_enzyme_metadata_curation_import_batch(
    req: EnzymeMetadataCurationBatchRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """Create or preview an internal archive batch for accepted metadata decisions."""
    try:
        if req.dry_run:
            preview = await preview_enzyme_metadata_curation_batch(
                session,
                record_ids=req.record_ids,
                family=req.family,
                record_type=req.record_type,
                limit=req.limit,
            )
            return preview
        batch = await create_enzyme_metadata_curation_batch(
            session,
            user_id=current_user["id"],
            record_ids=req.record_ids,
            family=req.family,
            record_type=req.record_type,
            limit=req.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "prepared", "batch": batch}


@router.get("/enzyme-metadata/curation-batches")
async def list_enzyme_metadata_curation_import_batches(
    status: str | None = Query(default=None),
    family: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """List internal metadata curation archive batches."""
    try:
        batches = await list_enzyme_metadata_curation_batches(session, status=status, family=family, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"count": len(batches), "batches": batches, "reviewer_user_id": current_user["id"]}


@router.patch("/enzyme-metadata/curation-batches/{batch_id}/archive")
async def archive_enzyme_metadata_curation_import_batch(
    batch_id: int,
    req: EnzymeMetadataCurationBatchArchiveRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_admin),
):
    """Archive a prepared metadata curation batch; external SQLite mutation remains blocked."""
    try:
        batch = await archive_enzyme_metadata_curation_batch(
            session,
            batch_id=batch_id,
            user_id=current_user["id"],
            confirmation=req.confirmation,
            reviewer_notes=req.reviewer_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if batch is None:
        raise HTTPException(status_code=404, detail="Metadata curation batch not found")
    return {"status": "archived", "batch": batch}


@router.get("/enzyme-dbs/{family}/search")
async def search_enzyme_db_family(
    family: str,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Search papers, variants, and measurements in one simplified enzyme evidence database."""
    if family not in SIMPLE_ENZYME_DATABASES:
        raise HTTPException(status_code=404, detail=f"Unknown enzyme database family: {family}")
    return search_simple_enzyme_db(family, q=q, limit=limit)


@router.get("/admin/readiness")
async def get_admin_data_readiness(current_user: dict = Depends(require_admin)):
    """Admin-only deploy_data readiness for the management console."""
    readiness = collect_deploy_data_readiness()
    return {
        **readiness,
        "admin": {
            "user_id": current_user["id"],
            "view": "data-management",
            "read_only": True,
        },
    }


@router.get("/admin/updates")
async def list_admin_deploy_data_updates(
    component: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(require_admin),
):
    """Filter deploy_data update manifests for the management console."""
    readiness = collect_deploy_data_readiness()
    manifests = readiness.get("updates", {}).get("manifests", [])
    filtered = []
    for item in manifests:
        if not isinstance(item, dict):
            continue
        if component and item.get("component") != component:
            continue
        if status and item.get("status") != status:
            continue
        filtered.append(item)
    return {
        "count": len(filtered[:limit]),
        "updates": filtered[:limit],
        "filters": readiness.get("updates", {}).get("filters", {}),
        "admin": {
            "user_id": current_user["id"],
            "view": "data-management-updates",
            "read_only": True,
        },
    }


def _deploy_data_import_command(req: DeployDataImportRequest) -> list[str]:
    cmd = [sys.executable, "scripts/import_deploy_data.py"]
    options = {
        "--annotations": req.annotations,
        "--sifts": req.sifts,
        "--pdb": req.pdb,
        "--alphafold": req.alphafold,
        "--foldseek-root": req.foldseek_root,
        "--foldseek-pdb": req.foldseek_pdb,
        "--foldseek-alphafold": req.foldseek_alphafold,
        "--foldseek-custom": req.foldseek_custom,
        "--smoke-pdb": req.smoke_pdb,
    }
    for flag, value in options.items():
        if value:
            cmd.extend([flag, value])
    if req.symlink:
        cmd.append("--symlink")
    return cmd


def _validate_import_sources(req: DeployDataImportRequest) -> list[dict[str, Any]]:
    sources = []
    for name, value in {
        "annotations": req.annotations,
        "sifts": req.sifts,
        "pdb": req.pdb,
        "alphafold": req.alphafold,
        "foldseek_root": req.foldseek_root,
        "foldseek_pdb": req.foldseek_pdb,
        "foldseek_alphafold": req.foldseek_alphafold,
        "foldseek_custom": req.foldseek_custom,
        "smoke_pdb": req.smoke_pdb,
    }.items():
        if not value:
            continue
        path = Path(value).expanduser()
        sources.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
                "kind": "directory" if path.is_dir() else ("file" if path.is_file() else "missing"),
            }
        )
    return sources


@router.post("/admin/import")
async def trigger_admin_deploy_data_import(
    req: DeployDataImportRequest,
    current_user: dict = Depends(require_admin),
):
    """Prepare or execute a deploy_data import. Real execution requires confirmation."""
    sources = _validate_import_sources(req)
    missing_sources = [source for source in sources if not source["exists"]]
    command = _deploy_data_import_command(req)
    plan = {
        "dry_run": req.dry_run,
        "requires_confirmation": True,
        "confirmation_token": DEPLOY_IMPORT_CONFIRMATION,
        "mode": "symlink" if req.symlink else "copy",
        "command": command,
        "sources": sources,
        "missing_sources": missing_sources,
        "admin": {
            "user_id": current_user["id"],
            "view": "data-management-import",
        },
    }
    if req.dry_run:
        return {"status": "planned", "plan": plan}
    if req.confirmation != DEPLOY_IMPORT_CONFIRMATION:
        raise HTTPException(400, f"Set confirmation to {DEPLOY_IMPORT_CONFIRMATION} to run a real import")
    if missing_sources:
        raise HTTPException(400, {"message": "Import sources are missing", "missing_sources": missing_sources})

    proc = subprocess.run(command, cwd=str(PROJECT_ROOT), text=True, capture_output=True, check=False)
    return {
        "status": "completed" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "plan": plan,
        "readiness": collect_deploy_data_readiness(),
    }


@router.get("/stats")
async def get_data_stats(
    session: AsyncSession = Depends(get_session),
):
    """Summary statistics for all integrated databases."""
    global _data_stats_cache
    now = time.monotonic()
    if (
        not settings.DEBUG
        and _data_stats_cache is not None
        and now - _data_stats_cache[0] < DATA_STATS_CACHE_TTL_SECONDS
    ):
        return _data_stats_cache[1]

    tables = [
        ("enzyme_records", EnzymeRecord),
        ("taxonomy", Taxonomy),
        ("ec_numbers", ECNumber),
        ("pdb_structures", PDBStructure),
        ("alphafold_structures", AlphaFoldStructure),
        ("kinetic_parameters", KineticParameter),
        ("stability_records", StabilityRecord),
        ("substrate_compounds", SubstrateCompound),
        ("reaction_equations", ReactionEquation),
        ("directed_evolution_entries", DirectedEvolutionEntry),
        ("pfam_domains", PfamDomain),
        ("domain_architecture", DomainArchitecture),
        ("interpro_entries", InterProEntry),
        ("enzyme_interpro_links", EnzymeInterProLink),
        ("catalytic_sites", CatalyticSite),
        ("catalytic_residues", CatalyticResidue),
        ("signal_peptide_predictions", SignalPeptidePrediction),
        ("database_crossrefs", DatabaseCrossRef),
    ]

    count_sql = "\nUNION ALL\n".join(
        f"SELECT '{name}' AS name, COUNT(*) AS count FROM {model.__tablename__}"
        for name, model in tables
    )
    rows = await session.execute(text(count_sql))
    stats = {str(row.name): int(row.count or 0) for row in rows}
    database_counts = dict(stats)

    readiness = collect_deploy_data_readiness()
    lipase_status = collect_lipase_db_status()
    asset_counts = _deploy_data_asset_counts(readiness, lipase_status)
    for name, asset_count in asset_counts.items():
        if not stats.get(name) and asset_count > 0:
            stats[name] = asset_count

    # Ingestion status
    rows = await session.execute(
        select(KVStore.key, KVStore.value).where(KVStore.key.like("ingest:%"))
    )
    ingest_state = {r[0]: r[1][:12] for r in rows.fetchall()}

    payload = {
        "counts": stats,
        "database_counts": database_counts,
        "asset_counts": asset_counts,
        "data_scope": "browser_stats_full_domain_plus_deploy_assets",
        "export_safe": False,
        "import_scope": {
            "deploy_data_import": "file_staging_only",
            "sqlite_to_pg_domain_import": "full_domain_restore_not_export_safe_not_training_safe_not_a_only",
        },
        "count_source": "database_with_deploy_data_fallback",
        "ingestion_hashes": ingest_state,
    }
    if not settings.DEBUG:
        _data_stats_cache = (now, payload)
    return payload


# =============================================================================
# Vector search
# =============================================================================
@router.get("/vector/search")
async def vector_search(
    q: str = Query(..., min_length=10, description="Protein sequence to search similar enzymes"),
    top_k: int = Query(20, ge=1, le=100),
):
    """Semantic enzyme search via ESM-2 embeddings + Zvec vector store."""
    try:
        from app.ml.vector_search import EnzymeVectorSearch
        vs = EnzymeVectorSearch()
        try:
            results = vs.search_by_sequence(q, top_k=top_k)
            return {"query_length": len(q), "results": results, "indexed_enzymes": vs.count()}
        finally:
            vs.close()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Vector search failed: {e}")


# =============================================================================
# Trigger ingestion
# =============================================================================
@router.post("/ingest/{source}")
async def trigger_ingestion(
    source: str,
    force: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    """Trigger data ingestion for a specific source (uniprot, pdb, pubchem, etc.)."""
    from app.data.ingestor_registry import ingest_source

    try:
        report = await ingest_source(source, session, force=force)
        return report.to_dict()
    except KeyError:
        raise HTTPException(404, f"Unknown data source: {source}")


# =============================================================================
# Helpers
# =============================================================================

def _compound_dict(c: SubstrateCompound) -> dict:
    return {
        "cid": c.pubchem_cid,
        "name": c.name,
        "iupac": c.iupac_name,
        "formula": c.molecular_formula,
        "weight": c.molecular_weight,
        "smiles": c.smiles,
        "inchi": c.inchi,
        "inchikey": c.inchikey,
        "xlogp": c.xlogp,
        "tpsa": c.tpsa,
    }
