"""Executor v1.6 — 去智能化执行引擎

职责收缩：
  - 基于规则选工具（不是推理）
  - 执行步骤
  - 错误处理（内部消化）
  - 仅返回执行结果，不含评分/判断

核心原则：
  Executor = 动作系统，不是思考系统
  不做"是否正确"的判断
  不做"是否继续"的决策
"""


class Executor:
    def __init__(self, agent, tool_registry: dict):
        self.agent = agent
        self.tools = tool_registry

    def plan_task(self, task_input: str) -> dict:
        return self.agent.plan(task_input)

    def execute_step(self, task_state, step: dict, context: dict) -> dict:
        step_id = step.get("id", context.get("step_index", 0) + 1)
        action = step.get("action", "")

        agent_output = self.agent.execute_step(step, context)
        tool_name = self._select_tool(action)
        tool_input = agent_output.get("output", action)

        step_result = self._call_tool(tool_name, tool_input)

        record = {
            "step_id": step_id,
            "action": action,
            "tool": tool_name,
            "tool_input": tool_input[:200],
            "tool_output": step_result,
        }
        task_state.add_step_record(record)

        # CBF 将在 kernel 层剥离除 step_id + output 外的所有字段
        return {
            "step_id": step_id,
            "output": step_result,
        }

    def _select_tool(self, action: str) -> str:
        """基于关键词规则选择工具（非推理）。"""
        action_lower = action.lower()
        kw = {
            "code_executor": ["代码", "执行", "计算", "运行", "python", "脚本", "编译", "测试", "单元测试"],
            "http_request": ["网络", "请求", "获取", "下载", "网页", "http", "api", "curl", "fetch"],
        }
        for tool, keywords in kw.items():
            if any(k in action_lower for k in keywords):
                if tool in self.tools:
                    return tool
        return "llm"

    def _call_tool(self, tool_name: str, tool_input: str) -> str:
        """调用工具并内部消化错误。"""
        tool = self.tools.get(tool_name)
        if not tool:
            return f"[工具不可用: {tool_name}]"

        try:
            raw = tool.call(tool_input)
        except Exception as e:
            return f"[工具错误] {tool_name}: {str(e)}"

        if isinstance(raw, dict):
            return raw.get("content", str(raw))
        return str(raw)
