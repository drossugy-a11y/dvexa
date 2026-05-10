"""Chat Runtime — 流式步骤执行 + WebSocket 实时推送

使用 StepStreamer 发射执行步骤，
通过 StreamEmitter 实时推送到 WebSocket。
"""

from __future__ import annotations

import logging
import time
import uuid
import threading
from typing import Any

from surface.chat.chat_dto import ChatMessageDTO, ChatResponseDTO
from surface.chat.stream_events import StreamEmitter
from runtime.step_streamer import StepStreamer
from runtime.step_events import StepType


class ChatRuntime:
    """AI 对话运行时。StepStreamer + StreamEmitter + 历史管理。"""

    def __init__(self, kernel: Any, observer: Any = None,
                 loop: Any = None,
                 step_streamer: StepStreamer | None = None):
        self._kernel = kernel
        self._loop = loop
        self._observer = observer
        self._streamer = step_streamer or StepStreamer()
        self._history: list[ChatMessageDTO] = []
        self._emitters: dict[str, StreamEmitter] = {}
        self._lock = threading.Lock()

    # ── 提交消息 ──────────────────────────────────────────────────────

    def submit_message(self, message: str) -> ChatResponseDTO:
        task_id = f"chat-{uuid.uuid4().hex[:12]}"
        emitter = StreamEmitter(task_id)
        self._emitters[task_id] = emitter

        # 追加用户消息到历史
        user_msg = ChatMessageDTO(
            role="user", content=message,
            timestamp=time.strftime("%H:%M:%S"),
            task_id=task_id,
        )
        self._history.append(user_msg)

        # 配置 StepStreamer WebSocket 推送
        def ws_push(payload: dict):
            emitter.emit_event_dict(payload)

        self._streamer.set_ws_push(ws_push)

        emitter.emit_stream_started()
        self._streamer.directive(
            title="Input received",
            content=message[:120],
        )

        # 后台线程执行
        def _run():
            assistant_content = ""
            try:
                if self._loop is not None:
                    result = self._loop.run(message)["kernel_result"]
                else:
                    result = self._kernel.run_task(message)

                status = result.get("status", "completed")

                if self._observer:
                    try:
                        self._observer(result)
                    except Exception as e:
                        logging.getLogger("dvexa.chat").warning("Observer failed: %s", e)

                if status == "failed":
                    emitter.emit_error(result.get("result", str(result)))
                    self._streamer.error(content=result.get("result", str(result)))
                else:
                    summary = result.get("result", "") or result.get("goal", "")
                    assistant_content = summary[:2000]
                    emitter.emit_complete(summary)
                    self._streamer.complete(content=summary[:200])

                # 追加 assistant 响应到历史（仅一次）
                if assistant_content:
                    assistant_msg = ChatMessageDTO(
                        role="assistant",
                        content=assistant_content,
                        timestamp=time.strftime("%H:%M:%S"),
                        task_id=task_id,
                    )
                    with self._lock:
                        has_assistant = any(
                            m.task_id == task_id and m.role == "assistant"
                            for m in self._history
                        )
                        if not has_assistant:
                            self._history.append(assistant_msg)

            except Exception as e:
                emitter.emit_stream_error(str(e))
                self._streamer.error(content=str(e))
            finally:
                emitter.emit_stream_completed()

                def _cleanup():
                    time.sleep(2)
                    self._emitters.pop(task_id, None)

                threading.Thread(target=_cleanup, daemon=True).start()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return ChatResponseDTO(
            task_id=task_id,
            status="accepted",
            content=message,
            timestamp=time.strftime("%H:%M:%S"),
        )

    # ── Emitter 访问 ──────────────────────────────────────────────────

    def get_emitter(self, task_id: str) -> StreamEmitter | None:
        return self._emitters.get(task_id)

    def set_emitter_websocket(self, task_id: str, ws: Any) -> None:
        emitter = self._emitters.get(task_id)
        if emitter:
            emitter.set_websocket(ws)

    def is_task_running(self, task_id: str) -> bool:
        emitter = self._emitters.get(task_id)
        if emitter:
            return not emitter.is_finalized
        return False

    def has_active_tasks(self) -> bool:
        return any(not e.is_finalized for e in self._emitters.values())

    # ── 历史 ──────────────────────────────────────────────────────────

    def get_chat_history(self, limit: int = 50) -> list[dict]:
        return [m.to_dict() for m in self._history[-limit:]]

    def get_task_events(self, task_id: str) -> list[dict]:
        emitter = self._emitters.get(task_id)
        if emitter:
            return emitter.get_events()
        return []
