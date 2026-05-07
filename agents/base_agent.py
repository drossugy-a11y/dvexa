import json


class BaseAgent:
    def __init__(self, llm_tool):
        self.llm_tool = llm_tool

    def plan(self, task_input: str) -> dict:
        system_prompt = (
            "你是一个任务规划器。分析用户任务并输出JSON格式的计划。\n\n"
            "输出格式：\n"
            '{\n'
            '  "goal": "任务目标简述",\n'
            '  "steps": [\n'
            '    {\n'
            '      "id": 1,\n'
            '      "action": "步骤描述",\n'
            '      "phase": "阶段名称",\n'
            '      "risk": "HIGH|MEDIUM|LOW",\n'
            '      "depends_on": []\n'
            '    }\n'
            '  ]\n'
            '}\n\n'
            "可用工具: llm（通用AI）、http_request（网络请求）、code_executor（Python代码执行）。\n"
            "规划要求：\n"
            "1. 将任务分解为多个阶段（phase），每个阶段有明确目标\n"
            "2. 每步标注风险等级：HIGH（可能出错/依赖外部）、MEDIUM、LOW（确定性操作）\n"
            "3. 标注步骤间依赖（depends_on为前置步骤id列表，无依赖则为空数组）\n"
            "4. 步骤id从1开始递增\n"
            "5. 输出必须是严格的JSON，不要任何额外文本"
        )
        prompt = f"任务：{task_input}"
        result = self.llm_tool.call(prompt, system_prompt=system_prompt)
        try:
            data = json.loads(result["content"])
            if "goal" in data and "steps" in data:
                return data
        except json.JSONDecodeError:
            pass
        return {
            "goal": "执行任务",
            "steps": [{"id": 1, "action": task_input, "phase": "执行", "risk": "LOW", "depends_on": []}],
        }

    def replan(self, original_input: str, failed_step: dict, error_msg: str):
        context_info = (
            f"失败步骤: {json.dumps(failed_step, ensure_ascii=False)}\n"
            f"错误信息: {error_msg}"
        )
        system_prompt = (
            "前一步执行失败，请重新规划剩余步骤。\n"
            "分析失败原因属于以下哪种类型：\n"
            "1. TOOL_ERROR：工具调用失败（网络、代码执行等）\n"
            "2. AGENT_ERROR：LLM输出不符合预期\n"
            "3. VALIDATION_ERROR：步骤输出验证不通过\n"
            "4. RETRY_EXHAUSTED：重试次数耗尽\n\n"
            "输出JSON格式：\n"
            '{"goal": "...", "failure_type": "TOOL_ERROR", "steps": [{"id": 1, "action": "..."}]}'
        )
        prompt = f"原始任务：{original_input}\n执行情况：{context_info}\n新计划JSON："
        result = self.llm_tool.call(prompt, system_prompt=system_prompt)
        try:
            data = json.loads(result["content"])
            if "goal" in data and "steps" in data:
                return data
        except json.JSONDecodeError:
            pass
        return None

    def execute_step(self, step: dict, context: dict) -> dict:
        action = step.get("action", step.get("input", ""))
        history = context.get("history", [])
        step_index = context.get("step_index", 0)
        total = context.get("total_steps", 1)

        history_summary = "\n".join(
            f"步骤{h['step_id']}: [{h.get('confidence','-')}] 工具={h.get('tool','?')} → {str(h.get('output',''))[:200]}"
            for h in history
        ) if history else "（尚无已执行步骤）"

        system_prompt = (
            f"你正在执行任务第 {step_index+1}/{total} 步。\n"
            f"已执行步骤：\n{history_summary}\n\n"
            "根据上下文执行当前步骤并返回结果。"
        )
        agent_output = self.llm_tool.call(action, system_prompt=system_prompt)
        output_text = agent_output.get("content", str(agent_output))

        confidence = self._compute_confidence(output_text)
        return {
            "tool": "llm",
            "input": action,
            "output": output_text,
            "confidence": confidence,
        }

    @staticmethod
    def _compute_confidence(output: str) -> float:
        if not output or output.isspace():
            return 0.0
        error_indicators = ["错误", "失败", "error", "fail", "exception", "无法", "sorry", "apologize"]
        lower = output.lower()
        indicator_count = sum(1 for ind in error_indicators if ind in lower)
        if indicator_count >= 3:
            return 0.0
        if indicator_count >= 1:
            return 0.3
        if len(output) < 10:
            return 0.5
        return 1.0
