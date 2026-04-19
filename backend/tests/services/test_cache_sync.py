from datetime import date
import json
import pytest
from unittest.mock import MagicMock

from app.core.redis.cache_chart import ChartCacheServiceSync


@pytest.fixture
def mock_redis(): 
    return MagicMock()

@pytest.fixture
def service(mock_redis):
    return ChartCacheServiceSync(redis=mock_redis)

def test_save_daily_chart_success(service, mock_redis): 
    """Test save in daily chart"""
    chart_date = date(2026, 3, 28)
    entries = [
        {"rank": 1, "track_id": 1, "title": "song 1", "play_count": 100}, 
        {"rank": 2, "track_id": 2, "title": "song 2", "play_count": 80},
    ]
    total_plays = 180

    result = service.save_daily_chart(chart_date, entries, total_plays)
    
    assert result is True
    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args[0]
    assert call_args[0] == "chart:daily:2026-03-28"

    assert call_args[1] == 86400

    saved_data = json.loads(call_args[2])
    assert saved_data["type"] == "daily"
    assert saved_data["total_plays"] == 180
    assert len(saved_data["entries"]) == 2

def test_save_daily_chart_redis_error(service, mock_redis): 
    """Error handling while save test"""
    mock_redis.setex.side_effect = Exception("Connection refused")

    result = service.save_daily_chart(date.today(), [], 0)

    assert result is False

def test_save_weekly_chart(service, mock_redis): 
    """Weekly chart saving test"""
    result = service.save_weekly_chart("2026-W03", [], 0)

    assert result is True
    mock_redis.setex.assert_called_once()
    assert mock_redis.setex.call_args[0][1] == 604800

def test_save_monthly_chart(service, mock_redis):
    """Monthly chart saving test"""
    result = service.save_monthly_chart("2026-03", [], 0)

    assert result is True
    assert mock_redis.setex.call_args[0][1] == 3672000

def test_invalidate(service, mock_redis): 
    result = service.invalidate("daily", "2026-03-28")

    assert result is True

    mock_redis.delete.assert_called_once_with("charts:daily:2026-03-28")
    