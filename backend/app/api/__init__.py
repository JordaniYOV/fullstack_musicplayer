from fastapi import APIRouter

from .routes.admin import admin_routes
from .routes.auth import auth_routes
from .routes.open import open_routes

all_routes = APIRouter( )

all_routes.include_router(admin_routes)
all_routes.include_router(auth_routes)
all_routes.include_router(open_routes)

__all__ = ["all_routes"]