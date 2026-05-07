import pytest
from core.state import TaskState, TaskStatus


class TestTaskState:
    def test_create_task_is_pending(self):
        task = TaskState("测试任务")
        assert task.status == TaskStatus.PENDING
        assert task.input == "测试任务"
        assert task.retry_count == 0

    def test_mark_planning(self):
        task = TaskState("测试任务")
        task.mark_planning()
        assert task.status == TaskStatus.PLANNING

    def test_mark_executing(self):
        task = TaskState("测试任务")
        task.mark_executing()
        assert task.status == TaskStatus.EXECUTING

    def test_mark_waiting(self):
        task = TaskState("测试任务")
        task.mark_waiting()
        assert task.status == TaskStatus.WAITING

    def test_mark_completed_sets_result(self):
        task = TaskState("测试任务")
        task.mark_completed("完成")
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "完成"

    def test_mark_failed_sets_error(self):
        task = TaskState("测试任务")
        task.mark_failed("出错了")
        assert task.status == TaskStatus.FAILED
        assert task.error == "出错了"

    def test_can_retry_within_limit(self):
        task = TaskState("测试任务")
        assert task.can_retry() is True
        task.increment_retry()
        assert task.can_retry() is True
        task.increment_retry()
        assert task.can_retry() is False

    def test_set_plan(self):
        task = TaskState("测试任务")
        steps = [{"id": 1, "action": "步骤1"}]
        task.set_plan("目标", steps)
        assert task.plan_goal == "目标"
        assert task.plan == steps

    def test_add_step_record(self):
        task = TaskState("测试任务")
        task.add_step_record({"step_id": 1, "output": "ok"})
        assert len(task.steps) == 1
        assert task.steps[0]["step_id"] == 1
