import uuid
from sqlmodel import Session, select

from app.models import User, UserCreate, UserUpdate

def craete_user(*, session: Session, user_create: UserCreate) -> User: 
    db_obj = User.model_validate(
        user_create, update
    )