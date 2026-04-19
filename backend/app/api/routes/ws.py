import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active[client_id] = websocket

    def disconnect(self, client_id: str) -> None:
        self.active.pop(client_id, None)

    async def send(self, client_id: str, data: dict[str, Any]) -> None:
        if ws := self.active.get(client_id):
            await ws.send_json(data)

    async def broadcast(self, data: dict[str, Any]) -> None:
        disconnected = []
        for cid, ws in list(self.active.items()):
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(cid)
        for cid in disconnected:
            self.disconnect(cid)


manager = ConnectionManager()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    await manager.connect(client_id, websocket)
    try:
        await manager.broadcast({"type": "user_joined", "client_id": client_id})
        while True:
            data = await websocket.receive_json()
            # Route message by type — extend this as needed
            msg_type = data.get("type", "unknown")
            if msg_type == "ping":
                await manager.send(client_id, {"type": "pong"})
            elif msg_type == "broadcast":
                await manager.broadcast({"type": "message", "from": client_id, "payload": data.get("payload")})
            else:
                await manager.send(client_id, {"type": "error", "message": f"Unknown type: {msg_type}"})
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast({"type": "user_left", "client_id": client_id})


@router.websocket("/ws")
async def websocket_anonymous(websocket: WebSocket) -> None:
    client_id = str(uuid.uuid4())
    await websocket_endpoint(websocket, client_id)
