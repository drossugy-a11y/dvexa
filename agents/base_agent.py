"""Base Agent — 选股策略规划器

支持四种策略模板：
  - value: 价值型（PE/PB/股息率/现金流）
  - growth: 成长型（营收增速/利润增速/ROE趋势）
  - quality: 质量型（毛利率/ROE/资产负债率/现金流质量）
  - comprehensive: 综合型（以上全部加权）
"""

from __future__ import annotations

import json
import re


STRATEGY_TEMPLATES = {
    "value": {
        "name": "价值型",
        "focus": ["PE", "PB", "股息率", "自由现金流", "EV/EBITDA"],
        "prompt": "重点关注估值是否低估、分红是否稳定、现金流是否充裕",
    },
    "growth": {
        "name": "成长型",
        "focus": ["营收增速", "净利润增速", "ROE趋势", "研发投入占比"],
        "prompt": "重点关注成长性是否持续、增速是否有加速趋势、行业空间是否足够",
    },
    "quality": {
        "name": "质量型",
        "focus": ["毛利率", "ROE", "资产负债率", "现金流质量"],
        "prompt": "重点关注盈利质量是否可靠、财务是否稳健、商业模式是否可持续",
    },
    "comprehensive": {
        "name": "综合型",
        "focus": ["PE", "PB", "ROE", "营收增速", "毛利率", "资产负债率", "股息率"],
        "prompt": "综合评估估值、成长、盈利、财务健康、质量五个维度",
    },
}


def safe_parse_plan(llm_output: str) -> dict | None:
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


class BaseAgent:
    def __init__(self, llm_tool):
        self.llm_tool = llm_tool

    def plan(self, task_input: str) -> dict:
        strategy = self._detect_strategy(task_input)
        template = STRATEGY_TEMPLATES.get(strategy, STRATEGY_TEMPLATES["comprehensive"])

        system_prompt = (
            "你是A股选股分析规划器。根据用户任务输出结构化分析计划。\n\n"
            f"当前策略：{template['name']}\n"
            f"关注指标：{', '.join(template['focus'])}\n"
            f"分析方向：{template['prompt']}\n\n"
            "输出严格JSON：\n"
            '{"goal": "分析目标", "strategy": "' + strategy + '", '
            '"steps": [\n'
            '  {"id": 1, "action": "步骤描述", "tool": "stock_data|financial|screener|analyst|comparator"}\n'
            ']}\n\n'
            "只输出JSON，不允许额外内容。"
        )

        result = self.llm_tool.call(task_input, system_prompt=system_prompt)
        data = safe_parse_plan(result.get("content", ""))
        if data:
            return data
        return {
            "goal": task_input,
            "strategy": strategy,
            "steps": [{"id": 1, "action": task_input, "tool": "analyst"}],
        }

    def replan(self, original_input: str, failed_step: dict, error_msg: str):
        prompt = (
            f"原始任务：{original_input}\n"
            f"失败步骤：{json.dumps(failed_step, ensure_ascii=False)}\n"
            f"错误：{error_msg}\n"
            "重新规划，输出JSON："
        )
        result = self.llm_tool.call(prompt, system_prompt="重新规划选股分析步骤，只输出JSON。")
        return safe_parse_plan(result.get("content", ""))

    def execute_step(self, step: dict, context: dict) -> dict:
        action = step.get("action", "")
        history = context.get("history", [])

        history_summary = ""
        if history:
            parts = [f"步骤{h.get('step_id', '?')}: {str(h.get('output', ''))[:200]}" for h in history]
            history_summary = "\n".join(parts)

        system_prompt = (
            "你正在执行选股分析的一步。\n"
            "根据上下文执行当前步骤，返回分析结果。\n"
            "只返回结果数据，不需要额外解释。"
        )
        prompt = action
        if history_summary:
            prompt = f"之前的分析结果：\n{history_summary}\n\n当前任务：{action}"

        agent_output = self.llm_tool.call(prompt, system_prompt=system_prompt)
        return {
            "tool": step.get("tool", "analyst"),
            "input": action,
            "output": agent_output.get("content", str(agent_output)),
        }

    @staticmethod
    def _detect_strategy(task_input: str) -> str:
        task_lower = task_input.lower()
        if any(kw in task_lower for kw in ["价值", "value", "低估", "pe低", "高股息", "分红"]):
            return "value"
        if any(kw in task_lower for kw in ["成长", "growth", "增速", "高增长", "科技", "新"]):
            return "growth"
        if any(kw in task_lower for kw in ["质量", "quality", "稳健", "白马", "龙头"]):
            return "quality"
        return "comprehensive"
