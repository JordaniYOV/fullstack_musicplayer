from datetime import datetime, timedelta
from typing import Any, Dict
import uuid

import redis.asyncio as redis

from app.models import Message

class TrackRedisManager(): 
    def __init__(self, redis: redis.Redis): 
        self.redis = redis
        self.popularity_key = "track:popularity"
        self.track_key = "track"
        self.album_key = "album"

    async def add_artist(self, artist_data: Dict[str, Any]) -> bool: 
        """
        Add popular artists
        """

        artist_id = artist_data.get("id")

        artist_key = f"artist:{artist_id}"

        data = { 
            "name": artist_data.get("name"), 
            "bio": artist_data.get("bio"), 
            "verifed": artist_data.get("verified")
        }

        await self.redis.hset(artist_key, data)

        stats_key = f"{artist_key}:stats"

        stats = { 
            "monthly_listeners": artist_data.get("monthly_listeners"),
            "plays": artist_data.get("plays"), 
            "followers": artist_data.get("followers")
        }

        await self.redis.hset(stats_key, stats)

        plays = int(artist_data.get("plays", 0))

        await self.redis.zadd("artist:popularity", {artist_key: plays})

    # async def get_album(self, album_key: str):
    #     if not await self.redis.exists(album_key): 
    #         return None
        
    #     album = await self.redis.hgetall(album_key)

    #     data = { 
    #         "track_id": album_key[6:], 
    #         **album
    #     }

    #     return data



    # async def add_album_of_populartrack(self, album: Dict[str, any]):
    #     album_id = album.get("id")

    #     album_key = f"{self.album_key}:{album_id}"

    #     if await self.get_album(album_key) is not None:
    #         return None

    #     data = {
    #         "album_cover": album.get("album_cover"),
    #         "album_name": album.get("album_name"),
    #         "artist": album.get("artist_name")
    #     }

    #     await self.redis.hset(album_key, mapping=data)

    async def add_track(self, track_data: Dict[str, Any], album_dict: Dict[str, Any]) -> bool:
        """
        Add popular tracks
        """

        track_id = track_data.get("id")
        
        track_key = f"{self.track_key}:{track_id}"

        data = {
            "track_name": track_data.get("track_name"),
            "duration_sec": track_data.get("duration_sec"), 
            "album_id": str(track_data.get("album_id")),
            "likes": track_data.get("likes"),
            "all_time_plays": track_data.get("all_time_plays"),
            "artist": track_data.get("artist"), 
            "cover":str(album_dict.get("cover_id"))
        }

        await self.redis.hset(track_key, mapping=data)

        # await self.add_album_of_populartrack(album_dict)

        # stats_key = f"{track_key}:stats"
        # initial_stats = { 
        #     "plays": track_data.plays, 
        #     "likes": track_data.likes
        # }

        # await self.redis.hset(stats_key, mapping=initial_stats)

        day_key = f"{self.popularity_key}:day"
        week_key = f"{self.popularity_key}:week"
        month_key = f"{self.popularity_key}:monthly"

        daily_plays = int(track_data.get("daily_plays", 0))
        weekly_plays = int(track_data.get("weekly_plays", 0))
        monthly_plays = int(track_data.get("monthly_plays", 0))

        await self.redis.zadd(day_key, {track_key: daily_plays})
        await self.redis.zadd(week_key, {track_key: weekly_plays})
        await self.redis.zadd(month_key, {track_key: monthly_plays})

    async def get_track(self, track_key: str): 
        """ 
        Get track info 
        """

        if not await self.redis.exists(track_key): 
            return None

        track = await self.redis.hgetall(track_key)

        # stats = await self.redis.hgetall(track_key)

        track_info = { 
            "track_id": track_key[6:], 
            **track, 
            # **stats,
        }

        return track_info


    async def get_popular_track(self, period: str, limit: int):
        """
        Get n popular tracks in given period
        """

        if period == "day": 
            track_keys = await self.redis.zrevrange(f"{self.popularity_key}:day", start=0, end=limit-1)

            return [await self.get_track(track_key) for track_key in track_keys]
        elif period == "week": 
            track_keys = await self.redis.zrevrange(f"{self.popularity_key}:week", start=0, end=limit-1)

            return [await self.get_track(track_key) for track_key in track_keys]
        elif period == "month": 
            track_keys = await self.redis.zrevrange(f"{self.popularity_key}:month", start=0, end=limit-1)

            return [await self.get_track(track_key) for track_key in track_keys]

        return Message(message="You set wrong period, there is day, week or month. Try agian")
        
    async def increase_plays(self, track_id: str, count: int): 
        """
        Increase track's plays by count
        """

        track_key = f"{self.track_key}:{track_id}"

        stats_key = f"{track_key}:stats"

        await self.redis.hincrby(stats_key, "plays", count)

        await self.redis.zincrby(f"{self.popularity_key}:day", count, track_key)
        await self.redis.zincrby(f"{self.popularity_key}:week", count, track_key)
        await self.redis.zincrby(f"{self.popularity_key}:month", count, track_key)
