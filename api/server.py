from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="DVexa v1.8")
kernel = None
_observer = None
_surface_ws = None


def set_surface_ws(ws):
    global _surface_ws
    _surface_ws = ws


# CORS — 允许前端开发服务器 (localhost:5173) 和构建产物
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    task: str


def set_kernel(k):
    global kernel
    kernel = k


def set_observer(fn):
    global _observer
    _observer = fn


def _response(success: bool, data=None, error: str | None = None, metadata: dict | None = None):
    return {
        "success": success,
        "data": data,
        "error": error,
        "metadata": metadata or {},
    }


@app.post("/task")
async def submit_task(req: TaskRequest):
    global kernel
    if not kernel:
        return _response(False, error="Kernel 未初始化")
    try:
        result = kernel.run_task(req.task)
        # Execution Report (v1.88) — 观察链
        if _observer:
            try:
                _observer(result)
            except Exception:
                pass  # 观察失败不影响主流程
        return _response(True, data=result)
    except Exception as e:
        return _response(False, error=str(e))


@app.get("/tasks")
async def list_tasks():
    global kernel
    if not kernel:
        return _response(False, error="Kernel 未初始化")
    tasks = kernel.memory.get_all()
    return _response(True, data=tasks, metadata={"total": len(tasks)})


@app.get("/health")
async def health():
    return _response(True, data={"status": "ok"})


@app.websocket("/ws/surface")
async def surface_websocket(ws: WebSocket):
    global _surface_ws
    if not _surface_ws:
        await ws.close(code=1011, reason="Surface not initialized")
        return
    try:
        await _surface_ws.connect(ws)
        while True:
            await ws.receive_text()  # keep-alive ping/pong
    except WebSocketDisconnect:
        _surface_ws.disconnect(ws)
    except Exception:
        if ws in getattr(_surface_ws, "_connections", []):
            _surface_ws.disconnect(ws)
