from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracks import DailyTop, MonthlyTop, PlayEvent, Track, ChartEntry, ChartResponse, TrendingTrack, WeeklyTop



class ChartService:
    def __init__(self, session: AsyncSession): 
        self.session = session

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