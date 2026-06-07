"""Executor — 选股执行引擎

支持三种执行模式：
  - execute_screening: 批量筛选
  - execute_deep_analysis: 个股深度分析
  - execute_comparison: 多股对比
"""

import json


class Executor:
    def __init__(self, agent, tool_registry: dict):
        self.agent = agent
        self.tools = tool_registry

    def plan_task(self, task_input: str) -> dict:
        return self.agent.plan(task_input)

    def execute_step(self, task_state, step: dict, context: dict) -> dict:
        step_id = step.get("id", context.get("step_index", 0) + 1)
        action = step.get("action", "")
        tool_name = step.get("tool", "analyst")

        agent_output = self.agent.execute_step(step, context)
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

        return {"step_id": step_id, "output": step_result}

    def execute_screening(self, query: dict) -> dict:
        screener = self.tools.get("screener")
        if not screener:
            return {"error": "screener tool not available"}
        stocks = screener.call(query)
        financial = self.tools.get("financial")
        analyst = self.tools.get("analyst")
        results = []
        for stock_code in stocks.get("codes", [])[:20]:
            data = financial.call({"action": "score", "stock_code": stock_code}) if financial else {}
            if analyst:
                ai = analyst.call({"action": "analyze", "stock_code": stock_code, "data": data})
                results.append(ai)
            else:
                results.append({"stock_code": stock_code, "scores": data})
        return {"screening_result": results, "total": len(results)}

    def execute_deep_analysis(self, stock_code: str) -> dict:
        stock_data = self.tools.get("stock_data")
        financial = self.tools.get("financial")
        analyst = self.tools.get("analyst")
        comparator = self.tools.get("comparator")

        info = stock_data.call({"action": "info", "stock_code": stock_code}) if stock_data else {}
        scores = financial.call({"action": "score", "stock_code": stock_code}) if financial else {}
        peers = comparator.call({"action": "ranking", "stock_code": stock_code}) if comparator else {}

        if analyst:
            result = analyst.call({
                "action": "analyze",
                "stock_code": stock_code,
                "data": {"info": info, "scores": scores, "peers": peers},
            })
            return result
        return {"stock_code": stock_code, "info": info, "scores": scores, "peers": peers}

    def execute_comparison(self, stock_codes: list) -> dict:
        stock_data = self.tools.get("stock_data")
        financial = self.tools.get("financial")
        analyst = self.tools.get("analyst")

        all_data = []
        for code in stock_codes:
            info = stock_data.call({"action": "info", "stock_code": code}) if stock_data else {}
            scores = financial.call({"action": "score", "stock_code": code}) if financial else {}
            all_data.append({"stock_code": code, "info": info, "scores": scores})

        if analyst:
            return analyst.call({"action": "compare", "stocks": all_data})
        return {"comparison": all_data}

    def _call_tool(self, tool_name: str, tool_input) -> dict:
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"tool not available: {tool_name}"}
        try:
            return tool.call(tool_input)
        except Exception as e:
            return {"error": str(e)}
