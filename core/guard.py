"""Control Boundary Filter（CBF）— 选股分析过滤器

只传递分析结论 + 评分 + 原始数据摘要。
过滤掉：LLM 的中间推理过程、token 使用详情、API 调用细节。
"""


class CBF:
    ALLOWED_FIELDS = {"step_id", "output"}

    @classmethod
    def sanitize(cls, result: dict) -> dict:
        return {k: v for k, v in result.items() if k in cls.ALLOWED_FIELDS}

    @classmethod
    def sanitize_analysis(cls, analysis: dict) -> dict:
        allowed = {
            "stock_code", "summary", "score", "action",
            "strengths", "risks", "valuation_assessment",
            "investment_logic", "scores", "info",
        }
        return {k: v for k, v in analysis.items() if k in allowed}
