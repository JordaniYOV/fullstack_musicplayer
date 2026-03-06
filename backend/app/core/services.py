from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlayEvent



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