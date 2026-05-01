from datetime import date, datetime, timedelta

from typing import Any, Dict, Optional, Sequence, Tuple
from sqlalchemy import and_, desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session
import redis.asyncio as aioredis

from app.logging_config import get_logger
from .decorators import log_chart_operation, LogConfig
from app.models.tracks import DailyTop, MonthlyTop, PlayEvent, Track, ChartEntry, ChartResponse, TrendingTrack, WeeklyTop
from app.core.redis.cache_chart import ChartCacheServiceAsync

loggerAsync = get_logger("app.services.charts", service="ChartServiceAsync", engine="psycopg3")

class ChartServiceAsync:
    def __init__(self, session: AsyncSession, redis: aioredis.Redis): 
        self.logger = loggerAsync.bind(instance_id=id(self))
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
            completed=completed, 
        )

        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)

        self.logger.info(
            "play_event_added",
            user_id=user_id,
            track_id=track_id,                
        )

        return event
    
    async def build_entries(self, rows: Sequence[Tuple[Any, Track]], chart_period: date | str, chart_type: str ): 
        entries: list[ChartEntry] = []
        total_plays = 0

        for top, track in rows:
            entries.append(ChartEntry(
                rank=f"{chart_type}_top".rank_position, 
                track_id=track.id, 
                title=track.title, 
                artist=track.artist, 
                play_count=top.play_count,
                unique_listeners=top.unique_listeners, 
                trend=top.trend, 
                previous_rank = await self.get_previous_rank(top, chart_period, chart_type), 
            ))
            
            total_plays += top.play_count
        return entries, total_plays

    @log_chart_operation(LogConfig(operation="get_daily_chart", chart_type="daily"))
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
            self.logger.info(
                "cache_hit", 
                chart_type="daily", 
                chart_date=chart_date.isoformat(),
                source="redis",
            )
            return await self.format_cached_response(cached_data, "daily", chart_date.isoformat())
        
        self.logger.info(
            "cache_miss", 
            chart_type="daily",
            chart_date=chart_date.isoformat(), 
            source="datetime",
        )

        query = (select(DailyTop, Track)
                .join(Track, DailyTop.track_id == Track.id)
                .where(DailyTop.chart_date == chart_date)
                .limit(limit=limit)
            )
        
        result = await self.session.execute(query)
        rows = result.all()

        if not rows: 
            if chart_date == date.today(): 
                return await self.calculate_daily_chart_on_fly(chart_date, limit)
            raise ValueError(f"No chart data for {chart_date}")
        
        entries, total_plays = await self.build_entries(rows, chart_date, "daily")

        return ChartResponse(
            chart_type="daily", 
            period=chart_date.isoformat(), 
            generated_at=datetime.now(),
            entries=entries, 
            total_plays=total_plays
        )
        
    @log_chart_operation(LogConfig(operation="get_weekly_chart", chart_type="weekly"))
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
            self.logger.info(
                "cache_hit", 
                chart_type="weekly", 
                chart_date=year_week.isoformat(),
                source="redis",
            )

            return await self.format_cached_response(cached_data, "weekly", year_week.isoformat())
        
        self.logger.info(
            "cache_miss", 
            chart_type="weekly",
            chart_date=year_week.isoformat(), 
            source="datetime",
        )

        query = ( 
            select(WeeklyTop, Track)
            .join(Track, WeeklyTop.track_id == Track.id)
            .where(WeeklyTop.year_week == year_week)
            .order_by(WeeklyTop.rank_position)
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.scalars().all()

        if not rows:
            raise ValueError(f"No chart data for {year_week}")

        entries, total_plays = await self.build_entries(rows, year_week, "weekly")

        return ChartResponse(
            chart_type="weekly", 
            period=year_week, 
            generated_at=datetime.now(), 
            entries=entries, 
            total_plays=total_plays
        )
        
    @log_chart_operation(LogConfig(operation="get_monthly_chart", chart_type="monthly"))
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
            self.logger.info(
                "cache_hit", 
                chart_type="weekly", 
                chart_date=year_month.isoformat(),
                source="redis",
            )
            return await self.format_cached_response(cached_data, "montlhy", year_month)
        
        self.logger.info(
            "cache_miss", 
            chart_type="weekly",
            chart_date=year_month.isoformat(), 
            source="datetime",
        )

        query = (
            select(MonthlyTop, Track)
            .join(Track, MonthlyTop.track_id == Track.id)
            .where(MonthlyTop.year_month == year_month)
            .order_by(MonthlyTop.rank_position)
            .limit(limit)
        )

        result = await self.session.execute(query)
        rows = result.all()

        if not rows:
            raise ValueError(f"No chart data for {year_month}")

        entries, total_plays = await self.build_entries(rows, year_month, "monthly")
        return ChartResponse(
            chart_type="monthly", 
            period=year_month, 
            generated_at=datetime.now(), 
            entries=entries, 
            total_plays=total_plays
        )
    
    @log_chart_operation(LogConfig(operation="get_trending"))
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

    @log_chart_operation(LogConfig(operation="calculation_on_fly", chart_type='daily'))   
    async def calculate_daily_chart_on_fly(self, chart_date: date, limit: int): 
        """
        Data agregation for current day
        """

        start_dt = datetime.combine(chart_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)

        self.logger.info(
            "gathering_play_events", 
            start=start_dt.isoformat(), 
            end=end_dt.isoformat(),
        )

        query = select(
                PlayEvent.track_id,
                func.count().label('play_count'),
                func.count(func.distinct(PlayEvent.user_id)).label('unique_listeners'),
                func.avg(PlayEvent.duration_listened).label('avg_duration')
            ).where(
                and_(
                    PlayEvent.played_at >= start_dt, 
                    PlayEvent.played_at < end_dt
                )
            ).group_by(PlayEvent.track_id).order_by(desc('play_count')).limit(limit)
        
        result = await self.session.execute(query)
        stats = result.all()

        self.logger.info(
            "plays_events_gathered", 
            events_found=len(stats),
        )

        track_ids = [row.track_id for row in stats]
        tracks_query = select(Track).where(Track.id.in_(track_ids))
        tracks_result = await self.session.execute(tracks_query)
        tracks_res = tracks_result.scalars().all()
        print(f"Query: {tracks_res}")
        tracks = {t.id: t for t in tracks_res}

        self.logger.info(
            "tracks_details_fetched", 
            tracks_resolved=len(tracks),
        )

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

        self.logger.info(
            "period_stats_query", 
            start=start.isoformat(), 
            end=end.isoformat(),
        )

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
        
        self.logger.info(
            "period_stats_result", 
            tracks_count=len(stats),
        )

        return stats
    
    async def get_previous_rank(self, track_id: int, current_date: date, chart_type: str) -> Optional[int]:
        """
        Recieve rank position in previous period
        """
        days = {
            "daily": 1, 
            "weekly": 7, 
            "monthly": 30
        }
    
        prev_date = current_date - timedelta(days=days.get(chart_type, 1))
        
        self.logger.debug(
            "previous_rank_query", 
            track_id=track_id,
            chart_type=chart_type,
            current_date=current_date.isoformat(), 
            previous_date=prev_date.isoformat(), 
        )

        query = select(DailyTop.rank_position).where(
            and_(
                DailyTop.chart_date == prev_date, 
                DailyTop.track_id == track_id
            )
        )
    
        result = await self.session.execute(query)
        row = result.scalar_one_or_none()

        self.logger.debug(
            "previous_rank_result", 
            track_id=track_id,
            previous_rank=row,
            found=row is not None,
        )

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

        self.logger.debug(
            "formatting_cached_response", 
            chart_type=chart_type,
            period=period,
            entries_count=len(cached.get("entries", []))
        )
        try:
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

            self.logger.debug(
                "cached_response_formatted", 
                chart_type=chart_type,
                period=period,
                entries_count=len(entries),
            )

            return ChartResponse(
                chart_type=chart_type, 
                period=period,
                generated_at=datetime.fromisoformat(cached["generated_at"]),
                entries=entries, 
                total_plays=cached["total_plays"],
            )
        except (KeyError, ValueError) as e:
            self.logger.error(
                "cached_response_corrupted", 
                chart_type=chart_type,
                period=period,
                error_type=type(e).__name__,
                error_message=str(e), 
                cahce_keys=list(cached.keys()), 
                exc_info=True,
            )
            raise ValueError(f"Corrupted cache data for {chart_type}/{period}: {e}")

loggerSync = get_logger("app.services.charts", service="ChartServiceSync", engine="psycopg3")

class ChartServiceSync:
    """
    For celery. Give aggregated data from db
    """

    def __init__(self, session: Session):
        self.session = session
        self.logger = loggerSync.bind(instance_id=id(self))

    def build_entries(self, result: Sequence[Tuple[Any, Track]]):
        entries = []
        total_plays = 0 

        for top, track in result:
            entry = {
                "rank": top.rank_position, 
                "track_id": track.id, 
                "title": track.title, 
                "album": track.album,
                "play_count": top.play_count,
                "unique_listeners": top.unique_listeners, 
                "avg_listen_duration": top.avg_listen_duration,
                "trend": top.trend, 
            }
            entries.append(entry)
            total_plays += top.play_count
            
        return entries, total_plays


    @log_chart_operation(LogConfig(operation="get_daily_chart", chart_type="daily"))
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
            self.logger.warning(
                "sync_chart_empty", 
                chart_type="daily", 
                chart_date=chart_date.isoformat(),
            )
            return {"entries": [], "total_plays": 0}
        
        entries, total_plays = self.build_entries(result, chart_date, "daily")

        return {
            "entries": entries, 
            "total_plays": total_plays, 
            "chart_date": chart_date.isoformat(),
        }
    @log_chart_operation(LogConfig(operation="get_weekly_chart", chart_type="weekly"))
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
            self.logger.warning(
                "sync_chart_empty", 
                chart_type="weekly", 
                chart_period=year_week, 
            )
            return {"entries": [], "total_plays": 0}
        
        entries, total_plays = self.build_entries(result)

        return {
            "entries": entries, 
            "total_plays": total_plays, 
            "chart_date": year_week
        }
    
    @log_chart_operation(LogConfig(operation="get_monthly_chart", chart_type="monthly"))
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
            self.logger.warning(
                "sync_chart_empty", 
                chart_type="monthly", 
                chart_prtiod=year_month,
            )
            return {"entreis": [], "total_plays": 0}
        
        entries, total_plays = self.build_entries(result)

        return { 
            "entries": entries, 
            "total_plays": total_plays, 
            "chart_date": year_month
        }
        