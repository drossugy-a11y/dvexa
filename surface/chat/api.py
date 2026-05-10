"""Chat API — POST /chat, GET /chat/history, WS /chat/stream"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from surface.chat.chat_runtime import ChatRuntime


class ChatRequest(BaseModel):
    message: str


def create_chat_router(runtime: ChatRuntime) -> APIRouter:
    router = APIRouter(prefix="/chat")

    @router.post("")
    async def submit_chat(req: ChatRequest):
        resp = runtime.submit_message(req.message)
        return {"success": True, "data": resp.to_dict()}

    @router.get("/history")
    async def chat_history(limit: int = 50):
        history = runtime.get_chat_history(limit=limit)
        return {"success": True, "data": history}

    @router.websocket("/stream")
    async def chat_stream(ws: WebSocket):
        await ws.accept()
        sub = None  # (task_id, last_event_count)
        try:
            while True:
                data = await ws.receive_text()
                if data.startswith("subscribe:"):
                    task_id = data[len("subscribe:"):].strip()
                    runtime.set_emitter_websocket(task_id, ws)
                    sub = (task_id, 0)
                elif data == "ping":
                    await ws.send_text('{"type":"pong"}')
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    return router
