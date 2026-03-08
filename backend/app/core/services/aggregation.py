from typing import Optional
from datetime import date, timedelta, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, func, and_, desc

from app.models.tracks import PlayEvent, DailyTop, WeeklyTop, MonthlyTop

class AggregationService:
    def __init__(self, session: AsyncSession): 
        self.session = session

    async def aggregate_daily(self, target_date: Optional[date] = None):
        """
        Daily top aggregation
        """

        if target_date is None: 
            target_date = date.today() - timedelta(days=1)

        start_dt = datetime.combine(target_date, datetime.min.time())   
        end_dt = start_dt + timedelta(days=1)

        stats_query = (
            select(
                PlayEvent.track_id, 
                func.count().label('play_count'), 
                func.count(func.distinct(PlayEvent.user_id)).label('unique_listeners'),
                func.avg(PlayEvent.duration_listened).label('avg_duration')
            )   .where(
                    and_(
                        PlayEvent.played_at >= start_dt, 
                        PlayEvent.played_at < end_dt
                )
                .group_by(PlayEvent.track_id)
                .order_by(desc('play_count'))
                .limit(100)
            )
        )     

        result = await self.session.execute(stats_query)
        rows = result.all()

        await self.session.execute(
            delete(DailyTop).where(DailyTop.chart_date == target_date)
        )

        yesterday = target_date - timedelta(days=1)
        yesterday_query = select(DailyTop).where(DailyTop.chart_date == yesterday)
        yesterday_result = await self.session.execute(yesterday_query)
        yesterday_ranks = { 
            row.track_id: row.rank_position
            for row in yesterday_result.scalars().all()
        }

        for rank, row in enumerate(rows, 1): 
            trend = await self.calculate_trend(row.track_id, rank, yesterday_ranks)

            daily_top = DailyTop(
                chart_date=target_date, 
                track_id=row.track_id, 
                play_count=row.play_count,
                unique_listeners=row.unique_listensers, 
                avg_listen_duration=float(row.avg_duration or 0), 
                rank_position=rank, 
                trend=trend
            )

            self.session.add(daily_top)

            await self.session.commit()
            print(f"Aggregated daily chart for {target_date}: {len(rows)} tracks")
            return len(rows)
        
    async def aggregate_weekly(self, target_week: Optional[date] = None): 
        """
       Create weekly top
        """
        if target_week is None:
            today = date.today()
            target_week = today.strftime("%Y-W%W")

            if today.weekday() != 6:
                target_week = (today - timedelta(days=7).strftime("%Y-W%W"))

        year, week = map(int, target_week.split('-W'))
        week_start = datetime.strptime(f'{year}-W{week}-1', '%Y-W%W-%W').date()
        week_end = week_start + timedelta(days=6)

        stats_query = (
            select(
                DailyTop.track_id, 
                func.sum(DailyTop.play_count).label('total_plays'), 
                func.sum(DailyTop.unique_listeners).label('total_listeners')
            )
                .where(
                    and_(
                        DailyTop.chart_date >= week_start, 
                        DailyTop.chart_date <= week_end
                    )
                )
                .group_by(DailyTop.track_id)
                .order_by(desc('total_plays'))
                .limit(100)
        )

        result = await self.session.execute(stats_query)
        rows = result.scalars().all()

        await self.session.execute(delete(WeeklyTop).where(WeeklyTop.year_week == target_week))

        for rank, row in enumerate(rows, 1):
            weekly_top = WeeklyTop(
                year_week=target_week, 
                week_start=week_start,
                week_end=week_end, 
                track_id=row.track.id, 
                play_count=row.total_plays, 
                unique_listeners=row.total_listeners, 
                rank_position=rank
            )

            self.session.add(weekly_top)

        await self.session.commit()
        print(f"Aggregated weekly chart for {target_week}: {len(rows)} tracks")
        return len(rows)

    async def aggregate_monthly(self, target_month: Optional[date] = None):
        """
        Create monthly top 
        """

        if target_month is None:
            target_month = date.today().strftime('%Y-%M')
            
        year, month = map(int,target_month.split('-'))
        month_start = date(year, month, 1)
        
        if month == 12: 
            month_end = date(year + 1, month, 1) - timedelta(days=1)
        else: 
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        stats_query = (
            select( 
                DailyTop.track_id, 
                func.sum(DailyTop.play_count).label('total_plays'),
                func.sum(DailyTop.unique_listeners).label('total_listeners')
            )
                .where(
                    and_(
                        DailyTop.chart_date >= month_start, 
                        DailyTop.chart_date < month_end
                    )
                )
                .group_by(DailyTop.track_id)
                .order_by(desc('total_plays'))
                .limit(100)
        )

        result = await self.session.execute(stats_query)
        rows = result.all()

        await self.session.execute(
            delete(MonthlyTop).where(MonthlyTop.year_month == target_month)
        )

        for rank, row in enumerate(rows, 1): 
            monthly_top = MonthlyTop(
                year_month=target_month, 
                month_start=month_start, 
                month_end=month_end, 
                track_id=row.track_id, 
                play_count=row.total_plays, 
                unique_listeners=row.total_listeners, 
                rank_position=rank
            )

            self.session.add(monthly_top)
        
        await self.session.commit()
        print(f'Aggregated monthly chart for {target_month}: {len(rows)} tracks')
        return len(rows)

    async def cleanup_old_events(self, days: int = 30): 
        """
        Cleanup old playevents
        """

        cutoff_date = datetime.now() - timedelta(days=days)

        result = await self.session.execute(
            delete(PlayEvent).where(PlayEvent.played_at < cutoff_date)
        )
        await self.session.commit()
        print(f"Cleaned up {result.rowcount} old play events")

        return result.rowcount

    async def calculate_trend(self,
                              track_id: int, 
                              current_rank: int,
                              previous_ranks: dict) -> int: 
        """
        Calculate trend: 1 (up), -1 (down), 0(same), None (new)    
        """

        if track_id not in previous_ranks: 
            return None
        
        prev_rank = previous_ranks[track_id]
        if current_rank < prev_rank: 
            return 1
        elif current_rank > prev_rank: 
            return -1
        else:
            return 0