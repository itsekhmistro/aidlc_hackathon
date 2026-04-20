from fastapi import APIRouter

from app.api.routes import (
    attachments,
    auth,
    friends,
    health,
    login,
    messages,
    personal,
    presence,
    rooms,
    sessions,
    unread,
    user_bans,
    users,
    ws,
)

api_router = APIRouter()

# Legacy routes (JWT-based, kept for compatibility)
api_router.include_router(health.router, tags=["health"])
api_router.include_router(login.router, tags=["auth-legacy"])
api_router.include_router(users.router, tags=["users-legacy"])
api_router.include_router(ws.router, tags=["websocket"])

# New cookie-session routes
api_router.include_router(auth.router)
api_router.include_router(sessions.router)
api_router.include_router(rooms.router)
api_router.include_router(messages.router)
api_router.include_router(attachments.router)
api_router.include_router(friends.router)
api_router.include_router(user_bans.router)
api_router.include_router(presence.router)
api_router.include_router(unread.router)
api_router.include_router(personal.router)
