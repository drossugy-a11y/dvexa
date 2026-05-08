import json
import re


def safe_parse_plan(llm_output: str) -> dict | None:
    """3-step robust JSON plan parser: direct → regex extraction → fallback."""
    # Step 1: direct JSON parse
    try:
        data = json.loads(llm_output)
        if isinstance(data, dict) and "goal" in data and "steps" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Step 2: extract JSON object via regex
    try:
        match = re.search(r"\{.*\}", llm_output, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and "goal" in data and "steps" in data:
                return data
    except (json.JSONDecodeError, AttributeError):
        pass

    return None


class BaseAgent:
    def __init__(self, llm_tool):
        self.llm_tool = llm_tool

    def plan(self, task_input: str) -> dict:
        system_prompt = (
            "你是一个任务规划器。分析用户任务并输出严格结构化执行计划。\n\n"
            "🚨 强约束（必须遵守）\n"
            "- 只能输出 JSON，不能有任何解释、注释、markdown\n"
            "- 不能输出多余文本\n"
            "- 输出必须可被 json.loads 直接解析\n\n"
            "📦 输出 Schema：\n"
            '{\n'
            '  "goal": "任务目标简述",\n'
            '  "steps": [\n'
            '    {\n'
            '      "id": 1,\n'
            '      "action": "步骤描述",\n'
            '      "type": "reasoning | tool | memory",\n'
            '      "tool": "llm | code_executor | http_request（可选）",\n'
            '      "input": "工具输入（可选）"\n'
            '    }\n'
            '  ]\n'
            '}\n\n'
            "🧭 规划规则：\n"
            "1. steps 从 1 开始递增，数量 3-7 步\n"
            "2. 每步必须明确 type：reasoning（推理）/ tool（工具调用）/ memory（记忆）\n"
            "3. tool 类型步骤必须包含 tool + input 字段\n"
            "4. reasoning 类型不允许包含 tool 字段\n\n"
            "🧠 工具选择规则：\n"
            "- code/计算 → code_executor\n"
            "- 信息获取 → llm\n"
            "- 记录/存储 → memory\n"
            "- 不确定 → reasoning\n\n"
            "📤 只输出 JSON，不允许任何额外内容。"
        )
        prompt = f"用户任务：{task_input}"
        result = self.llm_tool.call(prompt, system_prompt=system_prompt)
        data = safe_parse_plan(result["content"])
        if data is not None:
            return data
        return {
            "goal": task_input,
            "steps": [{"id": 1, "action": task_input, "type": "tool", "tool": "llm", "input": task_input}],
        }

    def replan(self, original_input: str, failed_step: dict, error_msg: str):
        context_info = (
            f"失败步骤: {json.dumps(failed_step, ensure_ascii=False)}\n"
            f"错误信息: {error_msg}"
        )
        system_prompt = (
            "前一步执行失败，请重新规划剩余步骤。\n"
            "分析失败原因类型：\n"
            "1. TOOL_ERROR：工具调用失败\n"
            "2. AGENT_ERROR：LLM输出不符合预期\n"
            "3. RETRY_EXHAUSTED：重试次数耗尽\n\n"
            "只输出JSON，严格符合以下Schema：\n"
            '{"goal": "...", "failure_type": "TOOL_ERROR", '
            '"steps": [{"id": 1, "action": "...", "type": "reasoning | tool | memory"}]}'
        )
        prompt = f"原始任务：{original_input}\n执行情况：{context_info}\n新计划JSON："
        result = self.llm_tool.call(prompt, system_prompt=system_prompt)
        data = safe_parse_plan(result["content"])
        if data is not None:
            return data
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
