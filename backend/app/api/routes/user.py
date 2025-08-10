from fastapi import APIRouter

router = APIRouter(prefix="/user", tags=["users"])


@router.post('/signup')
def register_user():
    
