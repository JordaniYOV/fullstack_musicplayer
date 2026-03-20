from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session
from redis.asyncio import aioredis

from app.models.tracks import DailyTop, MonthlyTop, PlayEvent, Track, ChartEntry, ChartResponse, TrendingTrack, WeeklyTop
from app.core.redis.cache_chart import ChartCacheServiceAsync, ChartChachServiceSync


class ChartService:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis): 
        self.session = session
        self.redis = redis
        self.cache = ChartCacheServiceAsync(self.redis)

    async def record_play(self, 
                          track_id: int, 
                          user_id: int, 
                          duration: int, 
                          completed: bool = False): 
        """
        Record play event in db
        """
        event = PlayEvent(
            track_id=track_id, 
            user_id=user_id,
            duration_listened=duration, 
            completed=completed
        )

        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
    
    async def get_daily_chart(self, 
                              chart_date: Optional[date] = None, 
                              limit: int = 10) -> ChartResponse: 
        """
        Get daily top
        """
        if chart_date is None: 
            chart_date = date.today()
        cached_data = await self.cache.get_daily_chart(chart_date)
        if cached_data:
            return await self.format_cached_response(cached_data, "daily", chart_date.isoformat())
        
        query = (select(DailyTop, Track)
                .join(Track, DailyTop.track_id == Track.id)
                .where(DailyTop.data == chart_date)
                .limit(limit=limit)
            )
        result = await self.session.execute(query)
        rows = result.scalars().all()

        if not rows: 
            if chart_date == date.today(): 
                return await self.calculate_daily_chart_on_fly(chart_date, limit)
           
            raise ValueError(f"No chart data for {chart_date}")
        entries = []
        total_plays = 0

        for daily_top, track in rows:
            entries.append(ChartEntry(
                rank=daily_top.rank_position, 
                track_id=track.id, 
                title=track.title, 
                artist=track.artist, 
                play_count=daily_top.play_count,
                unique_listeners=daily_top.unique_listeners, 
                trend=daily_top.trend, 
                previous_rank = await self.get_previous_rank(daily_top.track_id, chart_date), 
            ))
            
            total_plays += daily_top.play_count

        return ChartResponse(
            chart_type="daily", 
            period=chart_date.isoformat(), 
            genereted_at=datetime.now(),
            entries=entries, 
            total_plays=total_plays
        )
    
    async def get_weekly_chart(self, 
                               year_week: Optional[date] = None, 
                               limit: int = 10) -> ChartResponse:
        """
        Get weekly top
        """

        if year_week is None: 
            today = date.today()
            year_week = today.strftime("%Y-W%W")

        cached_data = await self.cache.get_weekly_chart(year_week.isoformat())
        
        if cached_data:
            return await self.format_cached_response(cached_data, "weekly", year_week.isoformat())
        
        query = ( 
            select(WeeklyTop, Track)
            .join(Track, WeeklyTop.track_id == Track.id)
            .where(WeeklyTop.year_week == year_week)
            .order_by(WeeklyTop.rank_position)
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.scalars().all()

        entries = []
        total_plays = 0

        for weekly_top, track in rows: 
            entries.append(ChartEntry(
                rank=weekly_top.rank_position, 
                track_id=track.id, 
                title=track.title, 
                artist=track.artist, 
                play_count=weekly_top.play_count, 
                unique_listeners=weekly_top.unique_listeners, 
                trend=weekly_top.trend
            ))
            total_plays += weekly_top.play_count

        return ChartResponse(
            chart_type="weekly", 
            period=year_week, 
            generated_at=datetime.now(), 
            entries=entries, 
            total_plays=total_plays
        )
    
    async def get_monthly_chart(self, 
                                year_month: Optional[str] = None, 
                                limit: int = 100) -> ChartResponse: 
        """
        Get monthly top
        """

        if year_month is None:
            year_month = date.today().strftime("%Y-%m")

        cached_data = await self.cache.get_monthly_chart(year_month)

        if cached_data: 
            return await self.format_cached_response(cached_data, "montlhy", year_month)
        
        query = (
            select(MonthlyTop, Track)
            .join(Track, MonthlyTop.track_id == Track.id)
            .where(MonthlyTop.year_month == year_month)
            .order_by(MonthlyTop.rank_position)
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.all()

        entries = []
        total_plays = 0

        for monthly_top, track in rows:
            entries.append(ChartEntry(
                rank=monthly_top.rank_position, 
                track_id=track.id, 
                title=track.title, 
                artist=track.artist, 
                play_count=monthly_top.play_count, 
                unique_listeners=monthly_top.unique_listeners
            ))

            total_plays += monthly_top.play_count

        return ChartResponse(
            chart_type="monthly", 
            period=year_month, 
            generated_at=datetime.now(), 
            entries=entries, 
            total_plays=total_plays
        )
    
    async def get_trending(self, 
                           hours: int = 24, 
                           limit: int = 20) -> list[TrendingTrack]:
        """
        Get trend tracks for the last hours 
        """

        now = datetime.now()
        current_period = now - timedelta(hours=hours)
        previous_period = current_period - timedelta(hours=hours)

        current_stats = await self.get_period_stats(current_period, now)
        previous_stats = await self.get_period_stats(previous_period, current_period)

        trending = []
        for track_id, current in current_stats.items(): 
            previous = previous_stats.get(track_id, {'plays': 0, 'rank': 999})
            
            if current['plays'] > 10: 
                velocity = (current['plays'] - previous['plays']) / max(previous['plays'], 1)

                if velocity > 0.5:

                    trending.append(TrendingTrack(
                        track_id=track_id, 
                        title=current['title'],
                        artist=current['artist'], 
                        current_rank=current['rank'], 
                        previous_rank=previous['rank'] if previous['plays'] > 0 else None, 
                        position_change=previous['rank'] - current['rank'] if previous['plays'] > 0 else 999, 
                        velocity=velocity
                    ))

        return sorted(trending, key=lambda x:x.velocity, reverse=True)[:limit]

    async def calculate_daily_chart_on_fly(self, chart_date: date, limit: int): 
        """
        Data agregation for current day
        """

        start_dt = datetime.combine(chart_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)

        query = select(
                PlayEvent.track_id,
                func.count().label('play_count'),
                func.avg(PlayEvent.duration_listened).label('avg_duration')
            ).where(
                and_(
                    PlayEvent.played_at >= start_dt, 
                    PlayEvent.played_at < end_dt
                )
            ).group_by(PlayEvent.track_id).order_by(desc('play_count')).limit(limit)
        

        result = await self.session.execute(query)
        stats = result.scalars().all()


        track_ids = [row.track_id for row in stats]
        tracks_query = select(Track).where(Track.id.in_(track_ids))
        tracks_result = await self.session.execute(tracks_query)
        tracks = {t.id: t for t in tracks_result.scalars().all()}

        entries = []
        total_plays = 0
        
        for rank, row in enumerate(stats, 1): 
            track = tracks.get(row.track_id)
            if track: 
                entries.append(ChartEntry(
                    rank=rank, 
                    track_id=track.id, 
                    title=track.title,
                    artist=track.artist, 
                    play_count=row.play_count,
                    unique_listeners=row.unique_listeners, 
                    trend=None
                ))
                total_plays += row.play_count
        
        return ChartResponse(
            chart_type="daily", 
            period=chart_date.isoformat(), 
            generated_at=datetime.now(),
            entries=entries, 
            total_plays=total_plays
        )
    
    async def get_period_stats(self, start: datetime, end: datetime):
        """
        Method for recieve period stats
        """

        query = (
            select(
                PlayEvent.track_id, 
                func.count().label('plays'), 
                Track.title, 
                Track.artist
            )
            .join(Track, PlayEvent.track_id == Track.id)
            .where(
                and_(
                    PlayEvent.played_at >= start, 
                    PlayEvent.played_at < end
                )
            )
            .group_by(PlayEvent.track_id, Track.title, Track.artist)
        )

        result = await self.session.execute(query)
        stats = {}

        for rank, row in enumerate(result.all(), 1):
            stats[row.track_id] = {
                'plays': row.plays, 
                'title': row.title, 
                'artist': row.artist, 
                'rank': rank
            }

        return stats
    
    async def get_previous_rank(self, track_id: int, current_date: date, chart_type: str) -> Optional[int]:
        """
        Recieve rank position in previous period
        """
        
        if chart_type == 'daily':
            prev_date = current_date - timedelta(days=1)
            query = select(DailyTop.rank_position).where(
                and_(
                    DailyTop.chart_date == prev_date, 
                    DailyTop.track_id == track_id
                )
            )
        else: 
            return None 
        
        result = await self.session.execute(query)
        row = result.scalar_one_or_none()
        return row
    
    async def format_cached_response(
            self, 
            cached: dict, 
            chart_type: str, 
            period: str
    ) -> ChartResponse:
        """
        Remake cache data fro answer
        """

        entries = [
            ChartEntry(
                rank=e["rank"], 
                track_id=e["track_id"], 
                title=e["title"], 
                artist=e["artist"], 
                play_count=e["play_count"], 
                unique_listeners=e["unique_listeners"], 
                trend=e.get("trend"), 
            )
            for e in cached["entries"]
        ]

        return ChartResponse(
            chart_type=chart_type, 
            period=period,
            generated_at=datetime.fromisoformat(cached["generated_at"]),
            entries=entries, 
            total_plays=cached["total_plays"],
        )
        

class ChartServiceSync:
    """
    For celery. Give aggregated data from db
    """

    def __init__(self, session: Session)
        self.session = session

    def get_daily(
            self, 
            chart_date: Optional[date] = None, 
            limit: int = 100
    ) -> Dict[str, Any]: 
        """
        Get raw chart data.
        Return dict for seraliziation (for cache))
        """

        if chart_date is None:
            chart_date = date.today()

        query = (
            select(DailyTop, Track)
            .join(Track, DailyTop.track_id == Track.id)
            .where(DailyTop.chart_date == chart_date)
            .order_by(DailyTop.rank_position)
            .limit(limit)
        )

        result = self.session.exec(query).all()

        if not result:
            return {"entries": [], "total_plays": 0}
        
        entries = []
        total_plays = 0 

        for daily_top, track in result:
            entry = {
                "rank": daily_top.rank_position, 
                "track_id": track.id, 
                "title": track.artist, 
                "album": track.album,
                "play_count": daily_top.play_count,
                "unique_listeners": daily_top.unique_listeners, 
                "avg_listen_duration": daily_top.avg_listen_duration,
                "trend": daily_top.trend, 
            }
            entries.append(entry)
            total_plays += daily_top.play_count
        
        return {
            "entries": entries, 
            "total_plays": total_plays, 
            "chart_date": chart_date.isoformat(),
        }
    
    def get_weekly(
            self,
            year_week: Optional[str] = None, 
            limit: int = 100
    ) -> Dict[str, Any]: 
        """
        Get raw chart data.
        Return dict for seraliziation (for cache))
        """

        if year_week is None:
            year_week = date.today().isoformat()

        query = (
            select(WeeklyTop, Track)
            .join(Track, WeeklyTop.track_id == Track.id)
            .where(WeeklyTop.chart_date == year_week)
            .order_by(WeeklyTop.rank_position)
            .limit(limit)
        )

        result = self.session.exec(query).all()

        if result is None:
            return {"entries": [], "total_plays": 0}
        
        entries = []
        total_plays = 0 

        for weekly_top, track in result:
            entry = {
                "rank": weekly_top.rank_position, 
                "track_id": track.id, 
                "title": track.artist, 
                "album": track.album,
                "play_count": weekly_top.play_count,
                "unique_listeners": weekly_top.unique_listeners, 
                "avg_listen_duration": weekly_top.avg_listen_duration,
                "trend": weekly_top.trend,
            }

            entries.append(entry)
            total_plays += weekly_top.play_count

        return {
            "entries": entries, 
            "total_plays": total_plays, 
            "chart_date": year_week
        }
    
    def get_montlhy(
            self, 
            year_month: Optional[str] = None,
            limit: int = 100
    ) -> Dict[str, Any]: 
        """
        Get raw chart data.
        Return dict for seraliziation (for cache))
        """

        if year_month is None: 
            year_month = date.today().isoformat()

        query = (
            select(MonthlyTop, Track)
            .join(Track, MonthlyTop.track_id == Track.id)
            .where(MonthlyTop.year_month == year_month)
            .order_by(MonthlyTop.rank_position)
            .limit(limit)
        )

        result = self.session.exec(query).all()

        if result is None:
            return {"entreis": [], "total_plays": 0}
        
        entries = []
        total_plays = 0

        for monthly_top, track in result:
            entry = {
                "rank": monthly_top.rank_position, 
                "track_id": track.id, 
                "title": track.artist, 
                "album": track.album,
                "play_count": monthly_top.play_count,
                "unique_listeners": monthly_top.unique_listeners, 
                "avg_listen_duration": monthly_top.avg_listen_duration,
                "trend": monthly_top.trend,
            }

            entries.append(entry)
            total_plays += monthly_top.play_count

        return { 
            "entries": entries, 
            "total_plays": total_plays, 
            "chart_date": year_month
        }