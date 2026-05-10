"""Tests for Chat API — endpoint 响应格式验证"""

from __future__ import annotations

import asyncio
import time
from surface.chat.chat_runtime import ChatRuntime
from surface.chat.api import create_chat_router


class _FakeKernel:
    def run_task(self, task_input: str):
        return {
            "status": "completed",
            "task_id": "test-1",
            "goal": "test goal",
            "result": "Task completed successfully",
            "retry_count": 0,
        }


class TestChatAPI:

    def setup_method(self):
        self.runtime = ChatRuntime(_FakeKernel())
        self.router = create_chat_router(self.runtime)

    def _post_chat(self, message: str) -> dict:
        for route in self.router.routes:
            if route.path == "/chat" and "POST" in route.methods:
                from surface.chat.api import ChatRequest
                return asyncio.run(route.endpoint(ChatRequest(message=message)))
        return {"success": False, "error": "Route not found"}

    def _get_history(self, limit: int = 50) -> dict:
        for route in self.router.routes:
            if route.path == "/chat/history" and "GET" in route.methods:
                return asyncio.run(route.endpoint(limit))
        return {"success": False, "error": "Route not found"}

    def test_submit_chat_returns_success(self):
        result = self._post_chat("hello")
        assert result["success"] is True
        data = result["data"]
        assert data["task_id"].startswith("chat-")
        assert data["status"] == "accepted"

    def test_submit_chat_returns_valid_response(self):
        result = self._post_chat("test message")
        data = result["data"]
        assert "task_id" in data
        assert "timestamp" in data
        assert data["role"] == "assistant"
        assert data["content"] == "test message"

    def test_chat_history_empty_initially(self):
        result = self._get_history()
        assert result["success"] is True
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 0

    def test_chat_history_after_submit(self):
        self._post_chat("msg1")
        time.sleep(0.2)
        result = self._get_history()
        assert result["success"] is True
        assert len(result["data"]) >= 1

    def test_chat_history_includes_both_roles(self):
        self._post_chat("msg1")
        time.sleep(0.3)
        history = self._get_history()["data"]
        roles = {m["role"] for m in history}
        assert "user" in roles
        assert "assistant" in roles

    def test_chat_history_respects_limit(self):
        for i in range(3):
            self._post_chat(f"msg-{i}")
        time.sleep(0.4)
        limited = self._get_history(limit=1)["data"]
        assert len(limited) <= 1
