"""Stream Event System — 事件发射器 + WebSocket 广播

每个 event 对应一个 timeline 步骤。
emit() → 立即推送 websocket + append 到事件日志。
"""

from __future__ import annotations

import json
import time
from typing import Any

from surface.chat.chat_dto import TimelineEventDTO


class StreamEmitter:
    """事件发射器。持有 websocket 引用时实时广播，否则仅记录。"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._events: list[TimelineEventDTO] = []
        self._ws = None
        self._finalized = False

    def set_websocket(self, ws):
        self._ws = ws

    def emit(self, event: TimelineEventDTO) -> None:
        if self._finalized:
            return
        event.task_id = self.task_id
        event.timestamp = event.timestamp or time.strftime("%H:%M:%S")
        self._events.append(event)
        if self._ws:
            try:
                import asyncio
                asyncio.ensure_future(self._ws.send_text(json.dumps(event.to_dict(), default=str)))
            except Exception:
                pass

    def emit_planning(self, goal: str) -> None:
        self.emit(TimelineEventDTO(
            event_type="planning_started", task_id=self.task_id,
            content=goal, status="running",
        ))

    def emit_governance(self, strategy: str, decision: str, reason: str = "") -> None:
        self.emit(TimelineEventDTO(
            event_type="governance_decision", task_id=self.task_id,
            strategy=strategy, decision=decision, reason=reason,
        ))

    def emit_tool(self, tool: str, status: str = "running", step_id: str = "",
                   content: str = "") -> None:
        self.emit(TimelineEventDTO(
            event_type="tool_execution", task_id=self.task_id,
            tool=tool, status=status, step_id=step_id, content=content,
        ))

    def emit_memory(self, detail: str = "") -> None:
        self.emit(TimelineEventDTO(
            event_type="memory_hit", task_id=self.task_id, content=detail,
        ))

    def emit_message_chunk(self, content: str, index: int = 0) -> None:
        """Incremental token append — 前端收到后追加到当前 assistant message。"""
        self.emit(TimelineEventDTO(
            event_type="message_chunk", task_id=self.task_id,
            content=content, step_id=str(index),
        ))

    def emit_complete(self, summary: str = "") -> None:
        self.emit(TimelineEventDTO(
            event_type="execution_complete", task_id=self.task_id,
            status="completed", content=summary,
        ))

    def emit_error(self, reason: str) -> None:
        self.emit(TimelineEventDTO(
            event_type="error", task_id=self.task_id, status="error", content=reason,
        ))

    def emit_stream_started(self) -> None:
        self.emit(TimelineEventDTO(
            event_type="stream_started", task_id=self.task_id, status="running",
        ))

    def emit_stream_completed(self) -> None:
        """强制 finalize — 确保前端锁释放。"""
        if self._finalized:
            return
        # Bypass _finalized check: emit the event BEFORE marking finalized
        event = TimelineEventDTO(
            event_type="stream_completed", task_id=self.task_id, status="completed",
        )
        event.task_id = self.task_id
        event.timestamp = event.timestamp or time.strftime("%H:%M:%S")
        self._events.append(event)
        if self._ws:
            try:
                import asyncio
                asyncio.ensure_future(self._ws.send_text(json.dumps(event.to_dict(), default=str)))
            except Exception:
                pass
        self._finalized = True

    def emit_stream_error(self, reason: str) -> None:
        if self._finalized:
            return
        event = TimelineEventDTO(
            event_type="stream_error", task_id=self.task_id, status="error", content=reason,
        )
        event.task_id = self.task_id
        event.timestamp = event.timestamp or time.strftime("%H:%M:%S")
        self._events.append(event)
        if self._ws:
            try:
                import asyncio
                asyncio.ensure_future(self._ws.send_text(json.dumps(event.to_dict(), default=str)))
            except Exception:
                pass
        self._finalized = True

    def get_events(self) -> list[dict]:
        return [e.to_dict() for e in self._events]

    @property
    def is_finalized(self) -> bool:
        return self._finalized
