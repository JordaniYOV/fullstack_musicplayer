from fastapi import APIRouter, UploadFile

from app.api.deps import SessionDep
from app.models.users import ArtistProfile, UserRole
from app.crud.user import get_user_by_email, create_user
from app.schemas.user import UserCreate

router = APIRouter(tags=["artist_private"])

@router.post('/add/artist')
async def add_artist(session: SessionDep,
                    photo: UploadFile, 
                    email: str,
                    artist_name: str, 
                    password: str,
                    bio: str | None = None, 
                    monthly_listeners: int = 120,
                    verified: bool = False,
): 
    """
    Add new Artist
    """
    image_type = photo.content_type
    image = await photo.read()
    
    user = await get_user_by_email(session=session, email=email)
    if not user:
        user_create = UserCreate(
            username=artist_name,
            email=email,
            role=UserRole.ARTIST, 
            password=password
        )
        user = await create_user(session=session, user_create=user_create)
        
    artist = ArtistProfile( 
        artist_name=artist_name, 
        bio=bio, 
        verified=verified,
        monthly_listeners=monthly_listeners,
        user_id=user.id
    )
    session.add(artist)
    await session.commit()
