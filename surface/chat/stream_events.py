"""Stream Event System — 事件发射器 + WebSocket 广播

每个 event 对应一个 timeline 步骤。
emit() → 立即推送 websocket + append 到事件日志。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from surface.chat.chat_dto import TimelineEventDTO

logger = logging.getLogger("dvexa.stream")


class StreamEmitter:
    """事件发射器。持有 websocket 引用时实时广播，否则仅记录。"""

    def __init__(self, task_id: str, loop: asyncio.AbstractEventLoop | None = None):
        self.task_id = task_id
        self._events: list[TimelineEventDTO | dict] = []
        self._ws: Any = None
        self._loop = loop
        self._finalized = False

    def set_websocket(self, ws: Any) -> None:
        self._ws = ws

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _send_ws(self, data: str) -> None:
        """推送 JSON 到 WebSocket。失败时记录日志，不抛出。"""
        if not self._ws or not self._loop:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._ws.send_text(data), self._loop)
        except Exception as e:
            logger.warning("WebSocket send failed: %s", e)

    def emit_event_dict(self, payload: dict) -> None:
        """直接发射 dict 格式的事件（供 StepStreamer 使用）。"""
        if self._finalized:
            return
        event = dict(payload)
        event["task_id"] = self.task_id
        event["timestamp"] = event.get("timestamp", time.strftime("%H:%M:%S"))
        self._events.append(event)
        self._send_ws(json.dumps(event, default=str))

    def emit(self, event: TimelineEventDTO) -> None:
        if self._finalized:
            return
        event.task_id = self.task_id
        event.timestamp = event.timestamp or time.strftime("%H:%M:%S")
        self._events.append(event)
        self._send_ws(json.dumps(event.to_dict(), default=str))

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
        if self._finalized:
            return
        event = TimelineEventDTO(
            event_type="stream_completed", task_id=self.task_id, status="completed",
        )
        event.task_id = self.task_id
        event.timestamp = event.timestamp or time.strftime("%H:%M:%S")
        self._events.append(event)
        self._send_ws(json.dumps(event.to_dict(), default=str))
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
        self._send_ws(json.dumps(event.to_dict(), default=str))
        self._finalized = True

    def get_events(self) -> list[dict]:
        return [e.to_dict() if hasattr(e, 'to_dict') else e for e in self._events]

    @property
    def is_finalized(self) -> bool:
        return self._finalized
