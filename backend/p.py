import traceback
import uuid
from datetime import datetime as _dt

try:
    from app.core.kafka.schemas import PlayEventMessage
    msg = PlayEventMessage(
        track_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        duration_listened=180,
        completed=True,
        played_at=_dt.now(),
    )
    print('OK:', msg)
except TypeError as e:
    traceback.print_exc()