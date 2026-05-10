"""DVX Surface API — FastAPI Router

只读 endpoint 集合，聚合系统状态供前端展示。
所有 endpoint 返回统一响应信封 {success, data, error, metadata}。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from surface.snapshot_builder import SystemSnapshotBuilder
from surface.state_cache import StateCache


def _ok(data: Any) -> dict:
    return {"success": True, "data": data, "error": None, "metadata": {}}


def _err(msg: str) -> dict:
    return {"success": False, "data": None, "error": msg, "metadata": {}}


def create_surface_router(
    snapshot_builder: SystemSnapshotBuilder,
    cache: StateCache | None = None,
    state_machine: Any = None,
) -> APIRouter:
    """创建 Surface APIRouter，注入依赖。"""
    router = APIRouter(prefix="/surface", tags=["surface"])
    _cache = cache or StateCache()

    @router.get("/snapshot")
    def get_snapshot() -> dict:
        cached = _cache.get("snapshot")
        if cached is not None:
            return _ok(cached)
        try:
            snap = snapshot_builder.build()
            result = snap.to_dict()
            _cache.set("snapshot", result, ttl=5)
            return _ok(result)
        except Exception as e:
            return _err(str(e))

    @router.get("/capabilities")
    def get_capabilities() -> dict:
        cached = _cache.get("capabilities")
        if cached is not None:
            return _ok(cached)
        try:
            snap = snapshot_builder.build()
            result = {
                "summary": snap.capability_summary,
                "node_count": snap.capability_summary.get("node_count", 0),
            }
            # 尝试从 registry 获取更多数据
            registry = getattr(snapshot_builder, "_capability_registry", None)
            if registry:
                try:
                    result["categories"] = registry.categories
                    result["source_types"] = registry.source_types
                except Exception:
                    pass
            _cache.set("capabilities", result, ttl=10)
            return _ok(result)
        except Exception as e:
            return _err(str(e))

    @router.get("/governance")
    def get_governance() -> dict:
        cached = _cache.get("governance")
        if cached is not None:
            return _ok(cached)
        try:
            snap = snapshot_builder.build()
            _cache.set("governance", snap.governance_status, ttl=5)
            return _ok(snap.governance_status)
        except Exception as e:
            return _err(str(e))

    @router.get("/evolution")
    def get_evolution() -> dict:
        cached = _cache.get("evolution")
        if cached is not None:
            return _ok(cached)
        try:
            snap = snapshot_builder.build()
            _cache.set("evolution", snap.evolution_report, ttl=10)
            return _ok(snap.evolution_report)
        except Exception as e:
            return _err(str(e))

    @router.get("/insight")
    def get_insight() -> dict:
        cached = _cache.get("insight")
        if cached is not None:
            return _ok(cached)
        try:
            snap = snapshot_builder.build()
            _cache.set("insight", snap.insight_report, ttl=10)
            return _ok(snap.insight_report)
        except Exception as e:
            return _err(str(e))

    @router.get("/metrics")
    def get_metrics() -> dict:
        cached = _cache.get("metrics")
        if cached is not None:
            return _ok(cached)
        try:
            snap = snapshot_builder.build()
            _cache.set("metrics", snap.metric_summary, ttl=5)
            return _ok(snap.metric_summary)
        except Exception as e:
            return _err(str(e))

    @router.get("/execution")
    def get_execution() -> dict:
        cached = _cache.get("execution")
        if cached is not None:
            return _ok(cached)
        try:
            snap = snapshot_builder.build()
            _cache.set("execution", snap.execution_history, ttl=10)
            return _ok(snap.execution_history)
        except Exception as e:
            return _err(str(e))

    if state_machine is not None:
        @router.get("/runtime-state")
        def get_runtime_state() -> dict:
            return _ok(state_machine.to_dict())

    return router
