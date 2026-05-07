import uuid
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING = "waiting"
    FAILED = "failed"
    COMPLETED = "completed"


class TaskState:
    def __init__(self, task_input: str):
        self.id = str(uuid.uuid4())
        self.input = task_input
        self.status = TaskStatus.PENDING
        self.plan_goal = None
        self.plan = None
        self.steps = []
        self.result = None
        self.retry_count = 0
        self.max_retries = 2
        self.error = None

    def set_plan(self, goal: str, steps: list):
        self.plan_goal = goal
        self.plan = steps

    def add_step_record(self, step_info: dict):
        self.steps.append(step_info)

    def mark_planning(self):
        self.status = TaskStatus.PLANNING

    def mark_executing(self):
        self.status = TaskStatus.EXECUTING

    def mark_waiting(self):
        self.status = TaskStatus.WAITING

    def mark_completed(self, result):
        self.status = TaskStatus.COMPLETED
        self.result = result

    def mark_failed(self, reason):
        self.status = TaskStatus.FAILED
        self.result = {"error": reason}
        self.error = reason

    def can_retry(self):
        return self.retry_count < self.max_retries

    def increment_retry(self):
        self.retry_count += 1
