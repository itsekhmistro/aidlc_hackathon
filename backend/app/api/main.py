from fastapi import APIRouter

from app.api.routes import health, login, users, ws

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(ws.router, tags=["websocket"])
api_router.include_router(login.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
