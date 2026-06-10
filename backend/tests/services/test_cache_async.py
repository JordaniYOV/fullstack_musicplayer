


from datetime import date
from unittest.mock import AsyncMock
import pytest
import pytest_asyncio

from app.core.redis.cache_chart import ChartCacheServiceAsync


@pytest_asyncio.fixture
async def mock_redis(): 
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get = AsyncMock()
    redis.setex = AsyncMock()
    redis.close = AsyncMock()
    return redis

@pytest_asyncio.fixture
async def service(mock_redis):
    return ChartCacheServiceAsync(redis=mock_redis)

async def test_get_daily_chart_cache_hit(service, mock_redis):
    """Test to get chart from cache (if have data) """

    chart_date = date(2026, 3, 28)
    cached_data = {
        "type": "daily", 
        "period": "2026-03-28", 
        "entries": [{"rank": 1, "title": "Test"}], 
        "total_plays": 1000,
    }
    mock_redis.get.return_value = '{"type": "daily", "period": "2026-03-28", "entries": [{"rank": 1, "title": "Test"}], "total_plays": 1000}'

    result = await service.get_daily_chart(chart_date)

    assert result == cached_data

    mock_redis.get.assert_called_once_with("charts:daily:2026-03-28")

async def test_get_daily_chart_cache_error(service, mock_redis): 
    """Error handling test"""
    chart_date = date(2026, 3, 28)
    mock_redis.get.side_effect = Exception("Connection refused")

    result = await service.get_daily_chart(chart_date)

    assert result is None

async def test_get_daily_chart_cache_miss(service, mock_redis):
    """Test to get chart from cache (if data is missing)"""
    chart_date = date(2026, 3, 28)
    mock_redis.get.return_value = None 

    result = await service.get_daily_chart(chart_date)

    assert result is None
    