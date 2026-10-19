"""PDB analysis API — upload, parse, and analyze protein structure files."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.llm_gateway import llm_gateway
from app.core.llm_registry import get_model_info
from app.core.security import get_current_user
from app.services.pdb_parser import parse_pdb
from app.services import storage
from app.tools.residue_mapping_sifts import residue_mapping_sifts
from app.tools.structure_search_foldseek import structure_search_foldseek

router = APIRouter()

MAX_PDB_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_PDB_EXTENSIONS = {"pdb", "ent", "cif"}


class PDBAnalyzeByNameRequest(BaseModel):
    object_name: str
    model: str | None = None


class PDBResidueMappingRequest(BaseModel):
    pdb_data: str
    pdb_id: str | None = None
    chain_id: str | None = None
    uniprot_id: str | None = None
    uniprot_start: int = 1


class PDBResidueMappingByNameRequest(BaseModel):
    object_name: str
    pdb_id: str | None = None
    chain_id: str | None = None
    uniprot_id: str | None = None
    uniprot_start: int = 1


class PDBStructureSearchRequest(BaseModel):
    pdb_data: str
    database: str = "pdb"
    max_results: int = 10


class PDBStructureSearchByNameRequest(BaseModel):
    object_name: str
    database: str = "pdb"
    max_results: int = 10


def _user_pdb_folder(user_id: int) -> str:
    return f"uploads/user_{user_id}/pdb"


def _assert_user_pdb_access(object_name: str, user_id: int) -> None:
    if not object_name.startswith(f"uploads/user_{user_id}/"):
        raise HTTPException(status_code=403, detail="Access denied for this file")


def _validate_pdb_content(filename: str, text: str) -> None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_PDB_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: .{ext}")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Not a valid PDB/CIF file")


def _require_parsed_protein(analysis: dict) -> None:
    """Do not report metadata-only or unsupported structures as parsed proteins."""
    if not analysis.get("total_atoms") or not analysis.get("total_residues") or not analysis.get("chains"):
        raise HTTPException(status_code=400, detail="No protein coordinates found in PDB/CIF file")


def _infer_pdb_id_from_object_name(object_name: str) -> str:
    stem = Path(object_name).name.rsplit(".", 1)[0].strip()
    return stem[:4] if len(stem) >= 4 else stem


async def _summarize_pdb_analysis(analysis: dict, model_id: str | None) -> dict:
    """Generate a short, model-driven structural summary for the PDB page."""
    model = get_model_info(model_id)
    if not model:
        return {}

    chains = analysis.get("chains", []) or []
    chain_preview = [
        {
            "chain_id": c.get("chain_id"),
            "residue_count": c.get("residue_count"),
            "atom_count": c.get("atom_count"),
        }
        for c in chains[:4]
        if isinstance(c, dict)
    ]
    payload = {
        "title": (analysis.get("header") or {}).get("title"),
        "method": analysis.get("method"),
        "deposited_date": analysis.get("deposited_date"),
        "total_atoms": analysis.get("total_atoms"),
        "total_residues": analysis.get("total_residues"),
        "resolution": analysis.get("resolution"),
        "r_factor": analysis.get("r_factor"),
        "space_group": analysis.get("space_group"),
        "b_factor_stats": analysis.get("b_factor_stats"),
        "b_factor_boundary": (
            "B-factor is a source-dependent raw PDB field. Its meaning is unknown unless the structure source and convention are established; "
            "do not infer thermostability, flexibility, or model confidence from it."
        ),
        "chains": chain_preview,
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a structural biology assistant. "
                "Write a concise Chinese summary of a PDB structure analysis. "
                "Focus on chain composition, experimental metadata, data limitations, and practical follow-up suggestions. "
                "Never infer thermostability, flexibility, or model confidence from B-factor alone. "
                "Keep it to 4 short bullet points."
            ),
        },
        {
            "role": "user",
            "content": f"PDB analysis JSON:\n{payload}",
        },
    ]

    try:
        response = await llm_gateway.complete(
            messages=messages,
            model_id=model_id,
            temperature=0.2,
            max_tokens=300,
        )
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not content:
            return {}
        return {
            "ai_summary": content,
            "summary_model": model.name,
            "summary_model_id": model.id,
        }
    except Exception:
        return {}


@router.post("/analyze")
async def analyze_pdb(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a PDB file, parse its structure, and return analysis.

    The file is stored in MinIO and parsed for structural metadata:
    chains, sequences, resolution, B-factors, and more.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    if len(content) > MAX_PDB_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit")

    text = content.decode("utf-8", errors="replace")
    _validate_pdb_content(file.filename, text)

    try:
        analysis = parse_pdb(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDB parsing failed: {e}")
    _require_parsed_protein(analysis)

    # Store in MinIO for later reference
    try:
        stored = await storage.upload_file(
            content,
            file.filename,
            content_type="chemical/x-pdb",
            folder=_user_pdb_folder(current_user["id"]),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        **analysis,
        "object_name": stored["object_name"],
        "download_url": stored.get("download_url"),
        "file_name": file.filename,
        "file_size": stored["size"],
    }


@router.post("/parse")
async def parse_pdb_text(
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    """Parse PDB text content directly without uploading to storage.

    Accepts JSON with a 'pdb_data' field containing the raw PDB text.
    """
    pdb_text = payload.get("pdb_data", "")
    if not pdb_text or not pdb_text.strip():
        raise HTTPException(status_code=400, detail="pdb_data is required")

    try:
        analysis = parse_pdb(pdb_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDB parsing failed: {e}")
    _require_parsed_protein(analysis)

    return analysis


@router.post("/mapping")
async def map_pdb_residues(
    payload: PDBResidueMappingRequest,
    current_user: dict = Depends(get_current_user),
):
    """Map raw PDB residue numbering to UniProt-style positions."""
    pdb_text = payload.pdb_data or ""
    if not pdb_text.strip():
        raise HTTPException(status_code=400, detail="pdb_data is required")

    _validate_pdb_content("input.pdb", pdb_text)
    return await residue_mapping_sifts(
        pdb_data=pdb_text,
        pdb_id=payload.pdb_id or "",
        chain_id=payload.chain_id or "",
        uniprot_id=payload.uniprot_id or "",
        uniprot_start=payload.uniprot_start,
    )


@router.post("/mapping-by-name")
async def map_pdb_residues_by_name(
    payload: PDBResidueMappingByNameRequest,
    current_user: dict = Depends(get_current_user),
):
    """Map residue numbering for an already-uploaded PDB object."""
    object_name = payload.object_name
    if not object_name:
        raise HTTPException(status_code=400, detail="object_name is required")
    _assert_user_pdb_access(object_name, current_user["id"])

    try:
        content = await storage.download_file(object_name)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))

    pdb_text = content.decode("utf-8", errors="replace")
    _validate_pdb_content(object_name, pdb_text)
    return await residue_mapping_sifts(
        pdb_data=pdb_text,
        pdb_id=payload.pdb_id or _infer_pdb_id_from_object_name(object_name),
        chain_id=payload.chain_id or "",
        uniprot_id=payload.uniprot_id or "",
        uniprot_start=payload.uniprot_start,
    )


@router.post("/structure-search")
async def search_structure_templates(
    payload: PDBStructureSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search structural templates from raw PDB text."""
    pdb_text = payload.pdb_data or ""
    if not pdb_text.strip():
        raise HTTPException(status_code=400, detail="pdb_data is required")

    _validate_pdb_content("input.pdb", pdb_text)
    return await structure_search_foldseek(
        pdb_data=pdb_text,
        database=payload.database,
        max_results=payload.max_results,
    )


@router.post("/structure-search-by-name")
async def search_structure_templates_by_name(
    payload: PDBStructureSearchByNameRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search structural templates for an already-uploaded PDB object."""
    object_name = payload.object_name
    if not object_name:
        raise HTTPException(status_code=400, detail="object_name is required")
    _assert_user_pdb_access(object_name, current_user["id"])

    try:
        content = await storage.download_file(object_name)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))

    pdb_text = content.decode("utf-8", errors="replace")
    _validate_pdb_content(object_name, pdb_text)
    return await structure_search_foldseek(
        pdb_data=pdb_text,
        database=payload.database,
        max_results=payload.max_results,
    )


@router.post("/analyze-by-name")
async def analyze_by_name(
    payload: PDBAnalyzeByNameRequest,
    current_user: dict = Depends(get_current_user),
):
    """Analyze an already-uploaded PDB file by its MinIO object_name."""
    object_name = payload.object_name
    if not object_name:
        raise HTTPException(status_code=400, detail="object_name is required")
    _assert_user_pdb_access(object_name, current_user["id"])

    try:
        content = await storage.download_file(object_name)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))

    text = content.decode("utf-8", errors="replace")
    _validate_pdb_content(object_name, text)
    try:
        analysis = parse_pdb(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDB parsing failed: {e}")
    _require_parsed_protein(analysis)

    summary = await _summarize_pdb_analysis(analysis, payload.model)
    return {**analysis, **summary}
