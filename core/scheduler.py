from core.state import TaskState, TaskStatus


class Scheduler:
    def __init__(self):
        pass

    def create_task(self, task_input: str) -> TaskState:
        task = TaskState(task_input)
        task.status = TaskStatus.PENDING
        return task

    def update_task(self, task: TaskState, step_result: dict):
        task.add_step_record(step_result)
