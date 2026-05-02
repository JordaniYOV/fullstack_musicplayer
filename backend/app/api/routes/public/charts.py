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

import re
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser
from app.core.services.charts import ChartServiceAsync
from app.models.play import PlayResponse

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