"""Tool Sandbox Rule（工具沙箱）

Tool 层契约（控制权锁定协议 v1.0 P3）：
  tool output == data, never == decision

约束：
  1. call() 的返回值必须是纯数据，不得包含控制信号
  2. tool 不得引用 kernel / executor / planner 任何模块
  3. tool 不得参与推理或流程判断
  4. tool 不得访问 context / history / state
"""


class Tool:
    def call(self, input_data) -> dict:
        raise NotImplementedError
