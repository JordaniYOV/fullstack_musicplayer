
import redis.asyncio as redis
import json

from typing import Optional, Any
from ..config import settings

class CacheService: 
    def __init__(self, redis_client: redis.Redis): 
        self.redis = redis_client

    async def get(self, key: str) -> Optional[Any]: 
        """ Get value with key"""

        try: 
            value = await self.redis.get(key)
            if value: 
                return json.loads(value)
        except (json.JSONDecodeError, TypeError): 
            return value
        
        return None
    
    async def set(
            self, 
            key: str, 
            value: Any, 
            ttl: Optional[int] = None
    ) -> bool: 
        """ value save """

        if isinstance(value, (dict, list, tuple, int, float, bool)): 
            value = json.dumps(value)
            
        expire = ttl or settings.cache_ttl
        return await self.redis.setex(key, expire, value)
        
    
    async def delete(self, key: str) -> bool: 
        """ key delete """

        return bool(await self.redis.delete(key))
    
    async def delete_pattern(self, pattern: str) -> int: 
        """delete with pattern"""

        keys = await self.redis.keys(pattern)
        
        if keys: 
            return await self.redis.delete(*keys)
        return 0

    async def get_ttl(self, key: str) -> int: 
        """ get left time of key"""

        return await self.redis.ttl(key)

    async def clear_all(self) -> bool: 
        """clear all db (danger!!!)"""

        return await self.redis.flushdb() 
    