"""Executor 测试 — v1.6 去智能化后

测试范围：
  - _select_tool：纯规则映射
  - _call_tool：IO 调用与错误消化
  - 不再测试 _validate_result（已移除）
"""

import pytest
from core.executor import Executor


class FakeAgent:
    def plan(self, task_input):
        return {"goal": "test", "steps": [{"id": 1, "action": task_input}]}

    def execute_step(self, step, context):
        return {"tool": "llm", "input": step.get("action"), "output": "ok", "confidence": 1.0}


class FakeTool:
    def call(self, input_data):
        return {"content": f"processed: {input_data}"}


class FakeTaskState:
    def __init__(self):
        self.steps = []

    def add_step_record(self, record):
        self.steps.append(record)


@pytest.fixture
def executor():
    agent = FakeAgent()
    tools = {"llm": FakeTool(), "code_executor": FakeTool(), "http_request": FakeTool()}
    return Executor(agent, tools)


class TestSelectTool:
    def test_code_executor_keywords(self, executor):
        for kw in ["执行", "运行python", "代码", "计算"]:
            assert executor._select_tool(kw) == "code_executor"

    def test_http_request_keywords(self, executor):
        for kw in ["网络请求", "获取URL", "下载文件", "调用API"]:
            assert executor._select_tool(kw) == "http_request"

    def test_default_to_llm(self, executor):
        assert executor._select_tool("随便聊聊") == "llm"

    def test_unmatched_falls_back_to_llm(self, executor):
        assert executor._select_tool("分析数据") == "llm"


class TestCallTool:
    def test_unknown_tool_returns_error(self, executor):
        result = executor._call_tool("nonexistent", "input")
        assert "不可用" in result

    def test_known_tool_returns_content(self, executor):
        result = executor._call_tool("llm", "hello")
        assert "processed: hello" in result

    def test_tool_exception_is_swallowed(self, executor):
        class BrokenTool:
            def call(self, _):
                raise RuntimeError("爆炸")
        executor.tools["broken"] = BrokenTool()
        result = executor._call_tool("broken", "x")
        assert "工具错误" in result
        assert "爆炸" in result


class TestExecuteStep:
    def test_returns_only_step_id_and_output(self, executor):
        task = FakeTaskState()
        step = {"id": 5, "action": "测试动作"}
        context = {"step_index": 0, "total_steps": 1, "history": []}

        result = executor.execute_step(task, step, context)

        assert set(result.keys()) == {"step_id", "output"}
        assert result["step_id"] == 5

    def test_records_step_in_task_state(self, executor):
        task = FakeTaskState()
        step = {"id": 1, "action": "测试"}
        context = {"step_index": 0, "total_steps": 1, "history": []}

        executor.execute_step(task, step, context)

        assert len(task.steps) == 1
        assert task.steps[0]["step_id"] == 1
