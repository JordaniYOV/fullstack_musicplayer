
import redis.asyncio as aioredis
import redis as syncredis
import json

from datetime import date, datetime
from typing import Optional, Any, Dict
from ..config import settings

class ChartChachServiceSync:
    """
    Sync veriosn for Celery (only set data in redis)
    """

    def __init__(self, redis: syncredis.Redis):
        self.redis = redis
        self.TTL_DAILY = 24 * 3600
        self.TTL_WEEKLY = 7 * 24 * 3600
        self.TTL_MONTHLY = 30 * 34 * 3600

    def save_daily_chart(
            self,
            chart_date: date, 
            entries: list[Dict[str, Any]], 
            total_plays, 
    ) -> bool:
        """
        Save daily chart in Redis
        """

        key = f"chart:daily:{chart_date.isoformat()}"

        data = { 
            "type": "daily", 
            "period": chart_date.isoformat(), 
            "generateda_at": datetime.now().isoformat(), 
            "total_plays": total_plays, 
            "entries": entries 
        }

        try: 
            self.redis.setex(
                key,
                self.TTL_DAILY,
                json.dumps(data, ensure_ascii=False)
            )
            logger.info(f"Cached daily chart: {chart_date} ({len(entries)} tracks)")
            return True
        except Exception as e:
            logger.error(f"Failed to cache daily chart: {e}")
            return False
        
    def save_weekly_chart(
            self, 
            year_week: str, 
            entries: list[Dict[str, Any]], 
            total_plays:int
    ) -> bool:
        """
        Save weekly chart
        """
        key = f"charts:weekly:{year_week}"

        data = { 
            "type": "weekly", 
            "period": year_week, 
            "generated_at": datetime.now().isoformat(), 
            "total_plays": total_plays, 
            "entries": entries
        }

        try: 
            self.redis.setes(key, self.TTL_WEEKLY, json.dumps(data, ensure_ascii=False))
            return True
        except Exception as e: 
            logger.error(f"Failed to cache weekly chart: {e}")
            return False
        
    def save_monthly_chart(
            self, 
            year_month: str, 
            entries: list[Dict[str, Any]], 
            total_plays: int
    ) -> bool:
        """
        Save monthly chart
        """
        key = f"charts:monthly:{year_month}"

        data = {
            "type": "monthly", 
            "period": year_month, 
            "generated_at": datetime.now().isoformat(), 
            "total_plays": total_plays,
            "entries": entries
        }

        try:
            self.redis.setex(key, self.TTL_MONTHLY, json.dumps(data, ensure_ascii=True))
            return True
        except Exception as e:
            logger.error(f"Failed to cache montly chart: {e}")
            return False
    
    def invalidate(
            self, 
            chart_type: str,
            period: str
    ) -> bool: 
        key = f"charts:{chart_type}:{period}"
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return False


class ChartCacheServiceAsync:
    """
    For FastApi (only reading)
    """
    def __init__(self, redis: aioredis.Redis): 
        self.redis = redis

    async def get_daily_chart(
            self, 
            chart_date: date
    ) -> Optional[Dict]: 
        """
        Get daily chart from cache
        """

        key = f"charts:daily:[chart_date.isoformat()]"

        try: 
            data = await redi.get(key)
            if data: 
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def get_weekly_chart(
            self, 
            year_week: str
    ) -> Optional[Dict]: 
        """
        Get weekly chart
        """

        key = f"charts:weekly:{year_week}"

        try: 
            data = await redis.get(key)
            return json.loads(data) if data else None
        except Exception as e: 
            logger.error(f"Redis get error: {e}")
            return None
        
    async def get_monthly_chart( 
            self,
            year_month: str
    ) -> Optional[Dict]: 
        key = f"charts:monthly:{year_month}"

        try:
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e: 
            logger.error(f"Redis get error: {e}")
            return None