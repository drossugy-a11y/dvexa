from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="DVexa v1.5")
kernel = None


class TaskRequest(BaseModel):
    task: str


def set_kernel(k):
    global kernel
    kernel = k


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
