from fastapi import APIRouter
from app.api.routes import auth, society, wing, flat, user, notifications
from app.modules.visitor.routes.visitor     import router as visitor_router
from app.modules.complaint.routes.complaint import router as complaint_router
from app.modules.amenity.routes.amenity     import router as amenity_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(society.router)
api_router.include_router(wing.router)
api_router.include_router(flat.router)
api_router.include_router(user.router)
api_router.include_router(notifications.router)
api_router.include_router(visitor_router)
api_router.include_router(complaint_router)
api_router.include_router(amenity_router)
