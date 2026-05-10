"""Chat Runtime — 流式步骤执行 + WebSocket 实时推送

使用 StepStreamer 发射执行步骤，
通过 StreamEmitter 实时推送到 WebSocket。
支持自适应路由：简单聊天直通，复杂任务走完整 runtime。
"""

from __future__ import annotations

import logging
import re
import time
import uuid
import threading
from typing import Any

from surface.chat.chat_dto import ChatMessageDTO, ChatResponseDTO
from surface.chat.stream_events import StreamEmitter
from runtime.step_streamer import StepStreamer
from runtime.step_events import StepType
from runtime.runtime_router import is_simple_conversation

logger = logging.getLogger("dvexa.chat")


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

        # 自适应路由：简单聊天直通，复杂任务走 runtime
        if is_simple_conversation(message):
            target = self._run_simple_chat
        else:
            target = self._run_full_runtime

        emitter.emit_stream_started()
        thread = threading.Thread(
            target=target,
            args=(message, task_id, emitter),
            daemon=True,
        )
        thread.start()

        return ChatResponseDTO(
            task_id=task_id,
            status="accepted",
            content=message,
            timestamp=time.strftime("%H:%M:%S"),
        )

    # ── 轻量聊天路径 ──────────────────────────────────────────────────

    def _run_simple_chat(self, message: str, task_id: str,
                         emitter: StreamEmitter) -> None:
        """简单聊天：直接 LLM 调用，跳过 runtime pipeline。

        如果 kernel 不支持直通（缺 executor/agent/llm_tool），
        自动回退到完整 runtime 路径。
        """
        executor = getattr(self._kernel, 'executor', None)
        agent = getattr(executor, 'agent', None) if executor else None
        llm_tool = getattr(agent, 'llm_tool', None) if agent else None

        if llm_tool is None:
            logger.info("Simple chat unavailable, falling back to full runtime")
            return self._run_full_runtime(message, task_id, emitter)

        try:
            result = llm_tool.call(message)
            content = result.get("content", str(result))

            emitter.emit_complete(content[:2000])

            with self._lock:
                self._history.append(ChatMessageDTO(
                    role="assistant",
                    content=content[:2000],
                    timestamp=time.strftime("%H:%M:%S"),
                    task_id=task_id,
                ))
        except Exception as e:
            logger.warning("Simple chat failed: %s", e)
            emitter.emit_error(str(e))
        finally:
            emitter.emit_stream_completed()
            self._schedule_cleanup(task_id)

    # ── 完整 Runtime 路径 ──────────────────────────────────────────────

    def _run_full_runtime(self, message: str, task_id: str,
                          emitter: StreamEmitter) -> None:
        """完整 runtime：通过 UnifiedRuntimeLoop 执行 7 阶段生命周期。"""
        # 配置 StepStreamer WebSocket 推送
        def ws_push(payload: dict):
            emitter.emit_event_dict(payload)
        self._streamer.subscribe(lambda step: emitter.emit_event_dict(step.to_dict()))

        self._streamer.directive(
            title="Input received",
            content=message[:120],
        )

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
                    logger.warning("Observer failed: %s", e)

            if status == "failed":
                err = result.get("result", str(result))
                err = re.sub(r"^步骤\d+:\s*", "", err, count=1)
                emitter.emit_error(err)
                self._streamer.error(content=err)
            else:
                summary = result.get("result", "") or result.get("goal", "")
                summary = re.sub(r"^步骤\d+:\s*", "", summary, count=1)
                assistant_content = summary[:2000]
                emitter.emit_complete(summary)
                self._streamer.complete(content=summary[:200])

            if assistant_content:
                with self._lock:
                    has_assistant = any(
                        m.task_id == task_id and m.role == "assistant"
                        for m in self._history
                    )
                    if not has_assistant:
                        self._history.append(ChatMessageDTO(
                            role="assistant",
                            content=assistant_content,
                            timestamp=time.strftime("%H:%M:%S"),
                            task_id=task_id,
                        ))

        except Exception as e:
            emitter.emit_stream_error(str(e))
            self._streamer.error(content=str(e))
        finally:
            emitter.emit_stream_completed()
            self._schedule_cleanup(task_id)

    def _schedule_cleanup(self, task_id: str) -> None:
        """2 秒后清理 emitter 引用。"""
        def _cleanup():
            time.sleep(2)
            self._emitters.pop(task_id, None)
        threading.Thread(target=_cleanup, daemon=True).start()

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
