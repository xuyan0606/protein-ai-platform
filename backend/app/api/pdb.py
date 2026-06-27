"""PDB analysis API — upload, parse, and analyze protein structure files."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.security import get_current_user
from app.services.pdb_parser import parse_pdb
from app.services import storage

router = APIRouter()

MAX_PDB_SIZE = 50 * 1024 * 1024  # 50 MB


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

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdb", "ent", "cif"):
        raise HTTPException(status_code=400, detail=f"Unsupported format: .{ext}")

    content = await file.read()
    if len(content) > MAX_PDB_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB limit")

    text = content.decode("utf-8", errors="replace")
    if not text.strip().startswith(("HEADER", "ATOM", "MODEL", "CRYST1", "TITLE", "REMARK")):
        raise HTTPException(status_code=400, detail="Not a valid PDB file")

    try:
        analysis = parse_pdb(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDB parsing failed: {e}")

    # Store in MinIO for later reference
    try:
        stored = await storage.upload_file(
            content,
            file.filename,
            content_type="chemical/x-pdb",
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

    return analysis


@router.post("/analyze-by-name")
async def analyze_by_name(
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    """Analyze an already-uploaded PDB file by its MinIO object_name."""
    object_name = payload.get("object_name", "")
    if not object_name:
        raise HTTPException(status_code=400, detail="object_name is required")

    try:
        content = await storage.download_file(object_name)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))

    text = content.decode("utf-8", errors="replace")
    try:
        analysis = parse_pdb(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDB parsing failed: {e}")

    return analysis