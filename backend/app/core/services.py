from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracks import DailyTop, PlayEvent, Track, ChartEntry, ChartResponse



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
                              limit: int = 10): 
        """
        Get daily top
        """
        if chart_date is None: 
            chart_date = date.today()

        query = select(DailyTop, Track).join(Track, DailyTop.track_id == Track.id).where(DailyTop.data == chart_date).limit(limit=limit)

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
                previous_rank=await self.get_previous_rank(daily_top.track_id, chart_date), 
            ))
            
            total_plays += daily_top.play_count

        return ChartResponse(
            chart_type="daily", 
            period=chart_date.isoformat(), 
            genereted_at=datetime.now(),
            entries=entries, 
            total_plays=total_plays
        )
    
    

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