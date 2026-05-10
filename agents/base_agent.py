"""Base Agent — DVX Runtime Agent with directive-aware planning

Detects SystemDirective in task_input and adjusts behavior:
- MUST_PLAN=True  → structured JSON planning (legacy mode)
- MUST_PLAN=False → simple chat response (no structured steps)
"""

from __future__ import annotations

import json
import re
from typing import Any


def safe_parse_plan(llm_output: str) -> dict | None:
    """3-step robust JSON plan parser: direct → regex extraction → fallback."""
    try:
        data = json.loads(llm_output)
        if isinstance(data, dict) and "goal" in data and "steps" in data:
            return data
    except json.JSONDecodeError:
        pass

    try:
        match = re.search(r"\{.*\}", llm_output, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and "goal" in data and "steps" in data:
                return data
    except (json.JSONDecodeError, AttributeError):
        pass

    return None


def _has_directive_flag(task_input: str, flag: str) -> bool:
    """检查 task_input 中是否包含 directive 标志。"""
    return flag in task_input[:300]


def _is_chat_mode(task_input: str) -> bool:
    """检测是否为 chat 模式（MUST_PLAN=False 或 MODE=chat）。"""
    return _has_directive_flag(task_input, "MUST_PLAN: False") or \
           _has_directive_flag(task_input, "MODE: chat") or \
           _has_directive_flag(task_input, "MODE: explore")


def _strip_directive(task_input: str) -> str:
    """从 task_input 中提取纯用户请求。"""
    if "User request:" in task_input:
        return task_input.split("User request:", 1)[-1].strip()
    if "用户请求：" in task_input:
        return task_input.split("用户请求：", 1)[-1].strip()
    return task_input


class BaseAgent:
    def __init__(self, llm_tool):
        self.llm_tool = llm_tool

    def plan(self, task_input: str) -> dict:
        if _is_chat_mode(task_input):
            return self._plan_chat(task_input)
        return self._plan_task(task_input)

    def _plan_chat(self, task_input: str) -> dict:
        """Chat 模式：简单位响应，无结构化规划。"""
        user_request = _strip_directive(task_input)
        system_prompt = (
            "You are a DVX Runtime Agent inside DVexa OS.\n"
            "You produce EXACTLY ONE consolidated response.\n"
            "Do NOT simulate multi-step conversations.\n"
            "Do NOT use numbered steps in your response.\n"
            "Do NOT generate continuation prompts.\n"
            "Produce a single, complete answer. Then stop."
        )
        result = self.llm_tool.call(user_request, system_prompt=system_prompt)
        output = result.get("content", str(result))

        return {
            "goal": output[:100],
            "steps": [{
                "id": 1,
                "action": output,
                "type": "reasoning",
            }],
        }

    def _plan_task(self, task_input: str) -> dict:
        """Task 模式：结构化 JSON 规划（原逻辑）。"""
        user_request = _strip_directive(task_input)
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
        result = self.llm_tool.call(user_request, system_prompt=system_prompt)
        data = safe_parse_plan(result["content"])
        if data is not None:
            return data
        return {
            "goal": user_request,
            "steps": [{"id": 1, "action": user_request, "type": "tool", "tool": "llm", "input": user_request}],
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
        original_clean = _strip_directive(original_input)
        prompt = f"原始任务：{original_clean}\n执行情况：{context_info}\n新计划JSON："
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

        # Chat mode: simple prompt without "第N步" language
        if total <= 1 and len(action) < 500:
            history_summary = ""
            if history:
                parts = [f"Previous: {str(h.get('output', ''))[:200]}" for h in history]
                history_summary = "\n".join(parts)

            system_prompt = (
                "You are a DVX Runtime Agent.\n"
                "Produce a single, complete response.\n"
                "Do NOT use numbered steps or multi-turn format."
            )
            if history_summary:
                prompt = f"Context:\n{history_summary}\n\nRespond to: {action}"
            else:
                prompt = action
        else:
            history_summary = "\n".join(
                f"Step {h['step_id']}: [{h.get('confidence','-')}] tool={h.get('tool','?')} → {str(h.get('output',''))[:200]}"
                for h in history
            ) if history else "（no prior steps）"

            system_prompt = (
                f"You are executing step {step_index+1}/{total}.\n"
                f"Prior steps:\n{history_summary}\n\n"
                "Execute the current step and return the result."
            )
            prompt = action

        agent_output = self.llm_tool.call(prompt, system_prompt=system_prompt)
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
