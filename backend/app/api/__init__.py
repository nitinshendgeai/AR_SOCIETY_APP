from fastapi import APIRouter
from app.api.routes import auth, society, wing, flat, user

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(society.router)
api_router.include_router(wing.router)
api_router.include_router(flat.router)
api_router.include_router(user.router)
