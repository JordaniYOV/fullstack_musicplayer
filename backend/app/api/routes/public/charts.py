"""
Public chart and play-event routes.
 
Endpoints
---------
POST   /charts/play                  Record a play event (auth required)
GET    /charts/play/history          Authenticated user's listen history
GET    /charts/daily                 Top 100 tracks for a given date
GET    /charts/weekly                Top 100 tracks for a given ISO week
GET    /charts/monthly               Top 100 tracks for a given month
GET    /charts/trending              Fastest-rising tracks in the last N hours
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, PlayEventServiceDep, SessionDep, RedisDep
from app.core.services.charts import ChartServiceAsync
from app.models.play import PlayResponse, PlayEventPublic
from app.models.tracks import ChartResponse, TrendingTrack

router = APIRouter(prefix="/charts", tags=["charts"])

def chart_service(session, redis) -> ChartServiceAsync:
    return ChartServiceAsync(session, redis)

@router.post(
    "/play", 
    response_model=PlayResponse, 
    summary="Record a play event", 
    description="Create a new play event for a track. Requires authentication."
)
async def record_play(
    payload: PlayResponse,
    current_user: CurrentUser, 
    play_service: PlayEventServiceDep,
):
    try:
        return await play_service.record_play(
            user_id=current_user.id,
            track_id=payload.track_id,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed ro record play: {exc}")
    
@router.get(
    "/play/history", 
    response_model=list[PlayEventPublic], 
    summary="Get user's listen history", 
    description="Retrieve the authenticated user's listen history, ordered by most recent plays."
)
async def get_listen_history(
    current_user: CurrentUser, 
    play_service: PlayEventServiceDep,
    limit: int = Query(default=100, ge=1, le=1000, description="Max number of play events to return"),
    offset: int = Query(default=0, ge=0, description="Number of play events to skip for pagination"),
): 
    events = await play_service.get_user_play_history(user_id=current_user.id, limit=limit, offset=offset)
    return events

@router.get(
    "/daily", 
    response_model=ChartResponse,
    summary="Daily top chart", 
    description="Returns the top tracks for the given date (default: today)"

)
async def get_daily_chart(
    session: SessionDep,
    redis: RedisDep,
    chart_date: Optional[date] = Query(
        default=None,
        description="ISO date (YYYY-MM-DD). Defaults to today", 
        example="2026-05-01"
    ), 
    limit: int = Query(default=100, ge=1, le=100),
):
    service = chart_service(session, redis)
    return await service.get_daily_chart(chart_date=chart_date,limit=limit)

@router.get(
    "/weekly", 
    response_model=ChartResponse,
    summary="Weekly top chart", 
    description="Returns the top tracks for the given ISO week (default: current week)"
)
async def get_weekly_chart(
    session: SessionDep, 
    redis: RedisDep,
    year_week: Optional[str] = Query(
        default=None, 
        description="ISO year and week (YYYY-Www). Defaults to current week", 
        example="2026-W18"
    ),
    limit: int = Query(default=100, ge=1, le=100),
)
    if year_week is None:
        import re 
        if not re.match(r"^\d{4}-W\d{2}$", year_week):
            raise HTTPException(status_code=422, detail="Invalid year_week format. Expected YYYY-Www")
    
    service = chart_service(session, redis)
    return await service.get_weekly_chart(year_week=year_week, limit=limit) 

@roter.get(
    "/monthly", 
    response_model=ChartResponse,
    summary="Monthly top chart", 
    description="Returns the top tracks for the given month (default: current month)"
)
async def get_monthly_chart(
    session: SessionDep, 
    redis: RedisDep,
    year_month: Optional[str] = Query(
        default=None, 
        description="Year and month (YYYY-MM). Defaults to current month", 
        example="2026-05"
    ),
    limit: int = Query(default=100, ge=1, le=100),
):
    if year_month is not None:
        import re 
        if not re.fullmatch(r"^\d{4}-\d{2}$", year_month):
            raise HTTPException(status_code=422, detail="Invalid year_month format. Expected YYYY-MM")
    
    service = chart_service(session, redis)
    return await service.get_monthly_chart(year_month=year_month, limit=limit)

@router.get(
    "/trending",
    response_model=list[TrendingTrack], 
    summary="Trending tracks",
    description="Returns the fastest-rising tracks."
)
async def get_trending(
    session: SessionDep, 
    redis: RedisDep,
    hours: int = Query(default=24, ge=1, le=168, description="Time window in hours to consider for trending calculation"),
    limit: int = Query(default=20, ge=1, le=50),
):
    service = chart_service(session, redis)
    return await service.get_trending(hours=hours, limit=limit)
