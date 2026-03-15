import redis.asyncio as aioredis
import redis as syncredis

from ..config import settings

# class AsyncRedisClient: 
#     def __init__(self): 
#         self.pool: Optional[aioredis.ConnectionPool] = None
#         self.client: Optional[aioredis.Redis] = None

#     async def init_pool(self): 
#         "Connection pool initialization"

#         self.pool = aioredis.ConnectionPool(
#             host=settings.redis_host, 
#             port=settings.redis_port, 
#             password=settings.redis_password, 
#             max_connections=settings.redis_max_connections,
#         )

#         self.client = aioredis.Redis(connection_pool=self.pool)
    
#     async def close_pool(self): 
#         "connection pool close"

#         if self.pool: 
#             await self.pool.disconnect()
    
#     async def get_client(self) -> aioredis.Redis: 
#         "get redis client"

#         if not self.client: 
#             await self.init_pool()
#         return self.client
    
#     async def ping(self) -> bool: 
#         "ping check"

#         try: 
#             client = await self.get_client()
#             return await client.ping()
#         except Exception: 
#             return False
        
#     async def health_check(self) -> dict: 
#         "check redis health"

#         is_healthy = await self.ping()
#         return {
#             "status": "healthy" if is_healthy else "unhealthy",
#             "connection": {
#                 "host": settings.redis_host, 
#                 "port": settings.redis_port
#             }
#         }
    
# async_redis_client = AsyncRedisClient()

async_redis_client: aioredis.Redis = None

async def get_async_redis() -> aioredis.Redis: 
    global async_redis_client
    if async_redis_client is None: 
        async_redis_client = aioredis.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True, 
           
        )
    return async_redis_client

async def close_async_redis():
    global async_redis_client
    if async_redis_client: 
        await async_redis_client.close()
        async_redis_client = None

sync_redis_client: syncredis.Redis = None

def get_sync_redis() -> syncredis.Redis:
    """
    Get senc Redis client (for celery)
    """
    global sync_redis_client
    if sync_redis_client is None: 
        sync_redis_client = syncredis.from_url(
            settings.redis_url,
            decode_response=True, 
            max_connections=settings.redis_max_connections,
        )
    return sync_redis_client

def close_sync_redis(): 
    global sync_redis_client
    if sync_redis_client: 
        sync_redis_client.close()
        sync_redis_client = None