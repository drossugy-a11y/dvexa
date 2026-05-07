import pytest
from core.kernel import DVexaKernel
from core.scheduler import Scheduler
from core.executor import Executor
from memory.memory_store import MemoryStore


class FakeAgent:
    def plan(self, task_input):
        return {
            "goal": "测试执行",
            "steps": [
                {"id": 1, "action": "第一步", "phase": "准备", "risk": "LOW", "depends_on": []},
            ],
        }

    def execute_step(self, step, context):
        return {"tool": "llm", "input": step.get("action"), "output": "执行成功", "confidence": 1.0}

    def replan(self, original, step, error):
        return None


class FakeTool:
    def call(self, input_data):
        return {"content": f"结果: {input_data}"}


@pytest.fixture
def kernel():
    agent = FakeAgent()
    tools = {"llm": FakeTool(), "code_executor": FakeTool(), "http_request": FakeTool()}
    executor = Executor(agent, tools)
    scheduler = Scheduler()
    memory = MemoryStore()
    return DVexaKernel(scheduler, executor, memory)


class TestKernel:
    def test_run_task_returns_result(self, kernel):
        result = kernel.run_task("测试任务")
        assert result["status"] in ("completed", "failed")
        assert "task_id" in result
        assert "steps" in result

    def test_memory_saves_after_run(self, kernel):
        kernel.run_task("记忆测试")
        tasks = kernel.memory.get_all()
        assert len(tasks) == 1
        assert tasks[0]["task_id"] is not None

    def test_multiple_tasks_saved(self, kernel):
        kernel.run_task("任务A")
        kernel.run_task("任务B")
        assert len(kernel.memory.get_all()) == 2
