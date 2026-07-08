"""
Search routes.

GET /search?q=queen&types=track,artist&limit=10

Parameters
----------
q       : required — search query string (min 1 char)
types   : optional comma-separated list of track|album|artist
          default: all three
limit   : results per entity type, 1–50, default 10
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import SessionDep
from app.core.services.search import SearchService, ALL_TYPES
from app.schemas.search import SearchResponse

router = APIRouter(tags=["search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search tracks, albums and artists",
    description=(
        "Performs a case-insensitive substring search across the catalog. "
        "Results within each type are ranked by popularity. "
        "Use `types` to restrict results to specific entity kinds."
    ),
)
async def search(
    session: SessionDep,
    q: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Search query string",
        example="bohemian",
    ),
    types: Optional[str] = Query(
        default=None,
        description="Comma-separated entity types: track, album, artist. Default: all.",
        example="track,artist",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Max results per entity type.",
    ),
):
    # Parse and validate type filter
    active_types = ALL_TYPES
    if types:
        requested = {t.strip().lower() for t in types.split(",")}
        invalid = requested - ALL_TYPES
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid type(s): {invalid}. Must be track, album, or artist.",
            )
        active_types = requested

    svc = SearchService(session)
    return await svc.search(query=q, types=active_types, limit=limit)