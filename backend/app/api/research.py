"""Read-only research governance evidence endpoints."""

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.tools.external_research_evidence import external_research_evidence

router = APIRouter()


@router.get("/evidence")
async def get_research_evidence(
    scope: str = Query("all"),
    current_user: dict = Depends(get_current_user),
):
    """Return local evidence status without allowing any governance mutation."""
    return external_research_evidence(scope)
