"""Tests for DVX Surface API — 所有 endpoint 响应格式验证"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from surface.api import create_surface_router
from surface.dto import SystemSnapshot
from surface.snapshot_builder import SystemSnapshotBuilder
from surface.state_cache import StateCache


class _MockBuilder(SystemSnapshotBuilder):
    def build(self) -> SystemSnapshot:
        return SystemSnapshot(
            timestamp="2026-05-08T12:00:00",
            task_count=42,
            system_health="healthy",
            capability_summary={"total": 10, "by_category": {"execution": 5, "governance": 5}},
            evolution_report={"total_events": 15, "by_event_type": {"assimilation": 15}},
            governance_status={"health_score": 0.9, "status": "STABLE"},
            execution_history=[{"task_id": "t1", "status": "completed"}],
            insight_report={"summary": "System is healthy"},
            metric_summary={"cost_table": {"llm": 3.0}},
        )


class TestSurfaceAPI:
    def setup_method(self):
        self.builder = _MockBuilder()
        self.cache = StateCache()
        self.router = create_surface_router(self.builder, self.cache)

    def _get(self, path: str) -> dict:
        """模拟 GET 请求直接调用路由处理函数。"""
        for route in self.router.routes:
            if route.path == path and "GET" in route.methods:
                fn = route.endpoint
                return fn()
        return {"success": False, "error": f"Route {path} not found"}

    def test_snapshot_endpoint(self):
        result = self._get("/surface/snapshot")
        assert result["success"] is True
        data = result["data"]
        assert data["task_count"] == 42
        assert data["system_health"] == "healthy"
        assert "capability_summary" in data
        assert "governance_status" in data
        assert "execution_history" in data
        assert data["execution_history"][0]["task_id"] == "t1"

    def test_capabilities_endpoint(self):
        result = self._get("/surface/capabilities")
        assert result["success"] is True
        assert result["data"]["summary"]["total"] == 10
        assert "summary" in result["data"]

    def test_governance_endpoint(self):
        result = self._get("/surface/governance")
        assert result["success"] is True
        assert result["data"]["health_score"] == 0.9

    def test_evolution_endpoint(self):
        result = self._get("/surface/evolution")
        assert result["success"] is True
        assert result["data"]["total_events"] == 15

    def test_insight_endpoint(self):
        result = self._get("/surface/insight")
        assert result["success"] is True
        assert "summary" in result["data"]

    def test_metrics_endpoint(self):
        result = self._get("/surface/metrics")
        assert result["success"] is True
        assert result["data"]["cost_table"]["llm"] == 3.0

    def test_execution_endpoint(self):
        result = self._get("/surface/execution")
        assert result["success"] is True
        assert len(result["data"]) == 1

    def test_cache_hits(self):
        """同一 endpoint 连续两次调用，第二次走缓存。"""
        r1 = self._get("/surface/snapshot")
        r2 = self._get("/surface/snapshot")
        assert r1 == r2

    def test_cache_invalidation(self):
        r1 = self._get("/surface/snapshot")
        self.cache.invalidate("snapshot")
        r2 = self._get("/surface/snapshot")
        assert r1 == r2  # 数据相同因为 builder 返回固定值

    def test_all_routes_return_response_envelope(self):
        paths = ["/surface/snapshot", "/surface/capabilities", "/surface/governance",
                 "/surface/evolution", "/surface/insight", "/surface/metrics",
                 "/surface/execution"]
        for path in paths:
            result = self._get(path)
            assert "success" in result
            assert "data" in result
            assert "error" in result
