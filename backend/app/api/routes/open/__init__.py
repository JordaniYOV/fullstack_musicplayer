from .login import router as login_route
from .registration import router as reg_route
from .search import router as search_route

from fastapi import APIRouter 

open_routes = APIRouter()

open_routes.include_router(login_route)
open_routes.include_router(reg_route)
open_routes.include_router(search_route)

__all__ = ["open_routes"]