"""Stock Analyst — LLM 驱动的股票分析

功能：
  - 单只股票深度 AI 分析
  - 批量筛选分析
  - 多股对比分析
"""

from __future__ import annotations

import json


class StockAnalyst:
    def __init__(self, llm_tool):
        self._llm = llm_tool

    def call(self, input_data) -> dict:
        if isinstance(input_data, str):
            input_data = {"action": "analyze", "stock_code": input_data}
        action = input_data.get("action", "analyze")

        if action == "analyze":
            return self.analyze_stock(
                input_data.get("stock_code", ""),
                input_data.get("data", {}),
            )
        elif action == "batch":
            return self.batch_screen(
                input_data.get("stocks", []),
                input_data.get("strategy", "comprehensive"),
            )
        elif action == "compare":
            return self.compare_stocks(input_data.get("stocks", []))
        return {"error": f"unknown action: {action}"}

    def analyze_stock(self, stock_code: str, data: dict) -> dict:
        data_text = json.dumps(data, ensure_ascii=False, default=str)[:3000]
        prompt = (
            f"分析以下A股股票：{stock_code}\n\n"
            f"数据：\n{data_text}\n\n"
            "请返回JSON格式分析结果：\n"
            '{"summary": "一句话总结(20字以内)",'
            '"investment_logic": "投资逻辑(2-3句话)",'
            '"strengths": ["优势1", "优势2"],'
            '"risks": ["风险1", "风险2"],'
            '"valuation_assessment": "低估/合理/偏高/高估",'
            '"score": 1-10的整数评分,'
            '"action": "重点关注/可以研究/暂时观望/建议回避"}'
        )
        result = self._llm.call(prompt, system_prompt="你是资深A股分析师，输出严格JSON。")
        content = result.get("content", "")
        try:
            parsed = json.loads(content)
            parsed["stock_code"] = stock_code
            return parsed
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    parsed["stock_code"] = stock_code
                    return parsed
                except json.JSONDecodeError:
                    pass
            return {"stock_code": stock_code, "summary": content[:200], "score": 5}

    def batch_screen(self, stocks_data: list, strategy: str) -> dict:
        stocks_text = json.dumps(stocks_data[:20], ensure_ascii=False, default=str)[:4000]
        prompt = (
            f"以下是按{strategy}策略筛选的A股候选股票数据：\n\n"
            f"{stocks_text}\n\n"
            "请按投资价值排序，返回JSON数组：\n"
            '[{"stock_code": "代码", "rank": 1, "reason": "推荐理由"}]'
        )
        result = self._llm.call(prompt, system_prompt="你是选股分析师，对候选股票排序，只输出JSON。")
        content = result.get("content", "")
        try:
            return {"strategy": strategy, "rankings": json.loads(content)}
        except json.JSONDecodeError:
            return {"strategy": strategy, "rankings": [], "raw": content[:500]}

    def compare_stocks(self, stocks_data: list) -> dict:
        stocks_text = json.dumps(stocks_data[:5], ensure_ascii=False, default=str)[:4000]
        prompt = (
            f"对比以下A股股票：\n\n{stocks_text}\n\n"
            "返回JSON格式对比结果：\n"
            '{"comparison": {"dimensions": {"估值": {"stock_code": "最优的代码"}, ...}},'
            '"recommendation": "综合推荐及理由"}'
        )
        result = self._llm.call(prompt, system_prompt="你是股票对比分析师，输出严格JSON。")
        content = result.get("content", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"recommendation": content[:500]}
