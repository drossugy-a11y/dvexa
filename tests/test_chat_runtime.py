"""Test ChatRuntime + StreamEmitter integration."""

import time
import threading
from surface.chat.chat_runtime import ChatRuntime
from surface.chat.chat_dto import ChatMessageDTO, TimelineEventDTO, ChatResponseDTO
from surface.chat.stream_events import StreamEmitter


class FakeKernel:
    """Minimal kernel stub for deterministic testing."""

    def __init__(self, delay: float = 0.0, fail: bool = False):
        self.delay = delay
        self.fail = fail

    def run_task(self, task_input: str):
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            return {"status": "failed", "result": "test error"}
        return {
            "status": "completed",
            "task_id": "test-1",
            "goal": "test goal",
            "plan": ["step1"],
            "steps": [{"step_id": 1, "tool": "test", "output": "done"}],
            "result": "Task completed successfully",
            "retry_count": 0,
        }


class TestChatRuntime:

    def test_submit_returns_accepted(self):
        runtime = ChatRuntime(FakeKernel())
        resp = runtime.submit_message("hello")
        assert resp.task_id.startswith("chat-")
        assert resp.status == "accepted"
        assert resp.role == "assistant"
        assert resp.content == "hello"

    def test_submit_appends_user_message(self):
        runtime = ChatRuntime(FakeKernel(delay=0.05))
        runtime.submit_message("test message")
        time.sleep(0.2)
        history = runtime.get_chat_history()
        assert len(history) >= 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "test message"

    def test_submit_appends_assistant_message_after_completion(self):
        runtime = ChatRuntime(FakeKernel(delay=0.05))
        runtime.submit_message("hello")
        time.sleep(0.3)
        history = runtime.get_chat_history()
        roles = [m["role"] for m in history]
        assert "assistant" in roles

    def test_get_emitter_returns_none_for_unknown(self):
        runtime = ChatRuntime(FakeKernel())
        assert runtime.get_emitter("nonexistent") is None

    def test_get_emitter_returns_emitter_for_active_task(self):
        runtime = ChatRuntime(FakeKernel())
        resp = runtime.submit_message("test")
        emitter = runtime.get_emitter(resp.task_id)
        assert emitter is not None
        assert isinstance(emitter, StreamEmitter)

    def test_set_emitter_websocket(self):
        runtime = ChatRuntime(FakeKernel())
        resp = runtime.submit_message("test")
        runtime.set_emitter_websocket(resp.task_id, "mock_ws")
        emitter = runtime.get_emitter(resp.task_id)
        assert emitter._ws == "mock_ws"

    def test_get_task_events_returns_list(self):
        runtime = ChatRuntime(FakeKernel(delay=0.1))
        resp = runtime.submit_message("test")
        time.sleep(0.05)
        events = runtime.get_task_events(resp.task_id)
        assert isinstance(events, list)
        # Should have stream_started as first event, then runtime_step
        assert len(events) >= 2
        assert events[0]["event_type"] == "stream_started"
        assert events[1]["event_type"] == "runtime_step"

    def test_get_task_events_empty_for_unknown(self):
        runtime = ChatRuntime(FakeKernel())
        assert runtime.get_task_events("nonexistent") == []

    def test_get_chat_history_respects_limit(self):
        runtime = ChatRuntime(FakeKernel(delay=0.05))
        for i in range(5):
            runtime.submit_message(f"msg-{i}")
        time.sleep(0.4)
        limited = runtime.get_chat_history(limit=2)
        assert len(limited) <= 2

    def test_emitter_emit_creates_events(self):
        emitter = StreamEmitter("test-task")
        emitter.emit(TimelineEventDTO(event_type="test", task_id="test-task"))
        assert len(emitter.get_events()) == 1
        assert emitter.get_events()[0]["event_type"] == "test"

    def test_emitter_emit_planning(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_planning("test goal")
        events = emitter.get_events()
        assert events[0]["event_type"] == "planning_started"
        assert events[0]["content"] == "test goal"

    def test_emitter_emit_governance(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_governance("BALANCED", "approve", "all good")
        events = emitter.get_events()
        assert events[0]["event_type"] == "governance_decision"
        assert events[0]["strategy"] == "BALANCED"
        assert events[0]["decision"] == "approve"

    def test_emitter_emit_tool(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_tool("test_tool", "running", "step-1", "doing work")
        events = emitter.get_events()
        assert events[0]["event_type"] == "tool_execution"
        assert events[0]["tool"] == "test_tool"

    def test_emitter_emit_complete(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_complete("done")
        events = emitter.get_events()
        assert events[0]["event_type"] == "execution_complete"
        assert events[0]["status"] == "completed"

    def test_emitter_emit_error(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_error("something broke")
        events = emitter.get_events()
        assert events[0]["event_type"] == "error"
        assert events[0]["status"] == "error"

    def test_emitter_emit_memory(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_memory("recalled pattern X")
        events = emitter.get_events()
        assert events[0]["event_type"] == "memory_hit"

    def test_emitter_to_dict_filters_empty(self):
        emitter = StreamEmitter("test-task")
        emitter.emit(TimelineEventDTO(event_type="test", task_id="test-task"))
        event = emitter.get_events()[0]
        # Empty fields like tool, status, strategy etc should be omitted
        assert "tool" not in event

    def test_runtime_with_observer(self):
        observed = []

        def observer(result):
            observed.append(result)

        runtime = ChatRuntime(FakeKernel(delay=0.05), observer=observer)
        runtime.submit_message("test")
        time.sleep(0.3)
        assert len(observed) >= 1

    def test_runtime_task_id_uniqueness(self):
        runtime = ChatRuntime(FakeKernel())
        r1 = runtime.submit_message("a")
        r2 = runtime.submit_message("b")
        assert r1.task_id != r2.task_id

    def test_runtime_get_emitter_websocket(self):
        runtime = ChatRuntime(FakeKernel())
        resp = runtime.submit_message("test")
        runtime.set_emitter_websocket(resp.task_id, "ws")
        e = runtime.get_emitter(resp.task_id)
        assert e is not None
        assert e._ws == "ws"

    def test_one_emitter_per_task(self):
        runtime = ChatRuntime(FakeKernel())
        r1 = runtime.submit_message("a")
        r2 = runtime.submit_message("b")
        e1 = runtime.get_emitter(r1.task_id)
        e2 = runtime.get_emitter(r2.task_id)
        assert e1 is not None
        assert e2 is not None
        assert e1.task_id != e2.task_id

    def test_emitter_stream_started(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_stream_started()
        events = emitter.get_events()
        assert events[0]["event_type"] == "stream_started"
        assert events[0]["status"] == "running"

    def test_emitter_stream_completed(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_stream_started()
        emitter.emit_stream_completed()
        events = emitter.get_events()
        ended = [e for e in events if e["event_type"] == "stream_completed"]
        assert len(ended) == 1
        assert ended[0]["status"] == "completed"

    def test_emitter_is_finalized_after_completed(self):
        emitter = StreamEmitter("test-task")
        assert not emitter.is_finalized
        emitter.emit_stream_completed()
        assert emitter.is_finalized

    def test_emitter_no_emit_after_finalized(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_stream_completed()
        emitter.emit_planning("should be ignored")
        events = emitter.get_events()
        assert all(e["event_type"] != "planning_started" for e in events)

    def test_emitter_message_chunk(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_message_chunk("Hello", 0)
        events = emitter.get_events()
        assert events[0]["event_type"] == "message_chunk"
        assert events[0]["content"] == "Hello"

    def test_emitter_stream_error(self):
        emitter = StreamEmitter("test-task")
        emitter.emit_stream_error("something broke")
        events = emitter.get_events()
        ended = [e for e in events if e["event_type"] == "stream_error"]
        assert len(ended) == 1
        assert ended[0]["status"] == "error"

    def test_runtime_stream_completed_in_events(self):
        runtime = ChatRuntime(FakeKernel(delay=0.05))
        resp = runtime.submit_message("test")
        time.sleep(0.3)
        events = runtime.get_task_events(resp.task_id)
        types = [e["event_type"] for e in events]
        assert "stream_completed" in types

    def test_runtime_no_duplicate_assistant(self):
        runtime = ChatRuntime(FakeKernel(delay=0.05))
        runtime.submit_message("test")
        time.sleep(0.3)
        history = runtime.get_chat_history()
        assistant_msgs = [m for m in history if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1

    def test_runtime_is_task_running(self):
        runtime = ChatRuntime(FakeKernel(delay=0.2))
        resp = runtime.submit_message("test")
        assert runtime.is_task_running(resp.task_id) is True
        time.sleep(0.5)
        assert runtime.is_task_running(resp.task_id) is False

    def test_runtime_has_active_tasks(self):
        runtime = ChatRuntime(FakeKernel(delay=0.2))
        assert runtime.has_active_tasks() is False
        runtime.submit_message("test")
        assert runtime.has_active_tasks() is True
        time.sleep(0.5)
        assert runtime.has_active_tasks() is False
