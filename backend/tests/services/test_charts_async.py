from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
import uuid

from app.core.redis.cache_chart import ChartCacheServiceAsync
from app.core.services.charts import ChartServiceAsync
from app.models.tracks import ChartResponse

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def mock_cache(): 
    cache = AsyncMock()
    cache.get_daily_chart = AsyncMock(return_value=None)
    cache.get_weekly_chart = AsyncMock(return_value=None)
    return cache

@pytest_asyncio.fixture
async def mock_redis(): 
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    return redis

@pytest_asyncio.fixture
async def service(async_session, mock_redis): 
    return ChartServiceAsync(async_session, mock_redis)

async def test_get_daily_chart_from_cache(service, mock_cache): 
    """Chart recieve from cache test"""
    service.cache = mock_cache
    cached_data = {
        "type": "daily", 
        "period": "2026-03-28", 
        "generated_at": datetime.utcnow().isoformat(), 
        "total_plays": 1000, 
        "entries": [
            {
                "rank": 1,
                "track_id": uuid.uuid4(),
                "title": "Test Song",
                "artist": "Test Artist",
                "play_count": 500,
                "unique_listeners": 300,
                "trend": 1,
            }
        ]
    }

    mock_cache.get_daily_chart.return_value = cached_data

    result = await service.get_daily_chart(date(2026, 3, 28))
    
    assert isinstance(result, ChartResponse)
    assert result.total_plays == 1000
    assert len(result.entries) == 1
    assert result.entries[0].title == "Test Song"

async def test_get_daily_chart_from_db(service, async_session, sample_tracks): 
    """Recieve chart from BD test (cache miss)"""
    from app.models.tracks import DailyTop
    chart_date = date.today() - timedelta(days=1)
    daily_top = DailyTop(
        chart_date=chart_date, 
        track_id=sample_tracks[0].id, 
        play_count=100, 
        unique_listeners=50, 
        rank_position=1, 
        trend=0,
    )

    async_session.add(daily_top)
    await async_session.commit()

    result = await service.get_daily_chart(chart_date)

    assert isinstance(result, ChartResponse)
    assert result.entries[0].track_id == sample_tracks[0].id
    assert result.entries[0].play_count == 100

async def test_get_daily_chart_not_found(service): 
    """Test when data is not found"""
    with pytest.raises(ValueError, match="No chart data"): 
        await service.get_daily_chart(date(2020, 1, 1))

async def test_get_daily_chart_calculate_on_fly(service, async_session, sample_plays_events): 
    """Test for aggregation on fly for daily chart"""
    today = date.today()

    from sqlalchemy import select   
    from app.models.tracks import PlayEvent
    result = await async_session.execute(select(PlayEvent))
    events = result.scalars().all()
    print(f"Events in DB: {len(events)}")  
    
    for event in sample_plays_events[:3]:
        print(f"Event date: {event.played_at.date()}, today: {today}")

    result = await service.get_daily_chart(today)

    assert isinstance(result, ChartResponse)
    assert len(result.entries) > 0

    plays = [e.play_count for e in result.entries]
    assert plays == sorted(plays, reverse=True)

async def test_calculate_on_fly_on_data(service):
    """Test for aggregation on fly when not events"""
    day = date.today() + timedelta(days=1)

    result = await service.calculate_daily_chart_on_fly(day, 100)

    assert len(result.entries) == 0
    assert result.total_plays == 0