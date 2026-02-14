import asyncio
from app.core.redis.redis import redis_client
from app.core.redis.track_manager import TrackRedisManager
from app.tasks.update_popular_tracks import update_list_task
from app.api.deps import SessionDep

async def test(): 

    redis = await redis_client.get_client()

    service = TrackRedisManager(redis)

    answer = await service.get_popular_track(period='day', limit=5)

    print(answer)

if __name__ == '__main__': 
    asyncio.run(test())
    # update_list_task.delay('day', 5)
