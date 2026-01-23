import redis.asyncio as redis

from typing import Optional

from ..config import settings

class RedisClient: 
    def __init__(self): 
        self.pool: Optional[redis.ConnectionPool] = None
        self.client: Optional[redis.Redis] = None

    async def init_pool(self): 
        "Connection pool initialization"

        self.pool = redis.ConnectionPool(
            host=settings.redis_host, 
            port=settings.redis_port, 
            password=settings.redis_password, 
            max_connections=settings.redis_max_connections,
        )

        self.client = redis.Redis(connection_pool=self.pool)
    
    async def close_pool(self): 
        "connection pool close"

        if self.pool: 
            await self.pool.disconnect()
    
    async def get_client(self) -> redis.Redis: 
        "get redis client"

        if not self.client: 
            await self.init_pool()
        return self.client
    
    async def ping(self) -> bool: 
        "ping check"

        try: 
            client = await self.get_client()
            return await client.ping()
        except Exception: 
            return False
        
    async def health_check(self) -> dict: 
        "check redis health"

        is_healthy = await self.ping()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "connection": {
                "host": settings.redis_host, 
                "port": settings.redis_port
            }
        }
    
redis_client = RedisClient()