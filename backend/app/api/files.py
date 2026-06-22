"""File upload/download API — MinIO-backed with JWT protection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.services import storage

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdb", ".fasta", ".fa", ".cif", ".sdf", ".mol", ".mol2", ".txt", ".csv"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.get("")
async def list_files(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """List uploaded files for the current user (from DB records)."""
    # Currently files are tracked via conversation context, not a standalone file table.
    # Return an empty list for now — frontend uses per-conversation file state.
    return []


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """Upload a file to MinIO object storage. Supports .pdb .fasta .cif .sdf etc."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB size limit")

    try:
        stored = await storage.upload_file(
            content,
            file.filename,
            content_type=file.content_type or "application/octet-stream",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "id": stored["object_name"],
        "name": file.filename,
        "size": stored["size"],
        "content_type": file.content_type,
        "download_url": stored.get("download_url"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/{object_name:path}/download")
async def download_file(
    object_name: str,
    current_user: dict = Depends(get_current_user),
):
    """Download a stored file directly."""
    from fastapi.responses import Response
    try:
        data = await storage.download_file(object_name)
        ext = object_name.rsplit(".", 1)[-1] if "." in object_name else "bin"
        media_types = {
            "pdb": "chemical/x-pdb",
            "fasta": "text/plain",
            "fa": "text/plain",
            "cif": "chemical/x-cif",
            "txt": "text/plain",
            "csv": "text/csv",
        }
        return Response(
            content=data,
            media_type=media_types.get(ext, "application/octet-stream"),
            headers={"Content-Disposition": f"attachment; filename={object_name.split('/')[-1]}"},
        )
    except RuntimeError as e:
        raise HTTPException(status_code=404 if "not found" in str(e).lower() else 500, detail=str(e))


@router.delete("/{object_name:path}")
async def delete_file(
    object_name: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a stored file."""
    try:
        deleted = await storage.delete_file(object_name)
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        return {"status": "deleted"}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
