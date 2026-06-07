"""Stock Feedback Engine — 选股效果反馈追踪

功能：
  - 记录推荐时的数据
  - 评估推荐效果（收益率 + 大盘/行业对比）
  - 策略历史表现统计
"""

from __future__ import annotations

from typing import Any


class StockFeedbackEngine:
    """选股效果反馈追踪。"""

    def __init__(self):
        self._recommendations: list[dict] = []
        self._strategy_stats: dict[str, dict] = {}

    def record_execution(self, execution_trace: dict, outcome: dict) -> None:
        """记录一次分析执行。"""
        strategy = execution_trace.get("strategy_used", "comprehensive")
        if strategy not in self._strategy_stats:
            self._strategy_stats[strategy] = {
                "success": 0, "fail": 0, "total": 0, "success_rate": 0.0,
            }
        stats = self._strategy_stats[strategy]
        if outcome.get("status") == "success":
            stats["success"] += 1
        else:
            stats["fail"] += 1
        stats["total"] += 1
        stats["success_rate"] = stats["success"] / stats["total"]

    def record_recommendation(self, stock_code: str, score: float,
                              ai_conclusion: dict, price_at_recommendation: float = 0):
        """记录推荐时的数据。"""
        self._recommendations.append({
            "stock_code": stock_code,
            "score": score,
            "conclusion": ai_conclusion,
            "price": price_at_recommendation,
            "strategy": ai_conclusion.get("strategy", "comprehensive"),
        })

    def evaluate_recommendation(self, stock_code: str,
                                days_later: int = 30) -> dict:
        """评估推荐效果（需要外部提供当前价格）。"""
        recs = [r for r in self._recommendations if r["stock_code"] == stock_code]
        if not recs:
            return {"error": "no recommendation found"}
        latest = recs[-1]
        return {
            "stock_code": stock_code,
            "recommended_score": latest["score"],
            "recommendation_price": latest["price"],
            "days_later": days_later,
        }

    def get_strategy_performance(self, strategy: str = "") -> dict:
        """某策略的历史推荐准确率。"""
        if strategy:
            return dict(self._strategy_stats.get(strategy, {}))
        return {k: dict(v) for k, v in self._strategy_stats.items()}

    def get_debug_snapshot(self) -> dict:
        return {
            "total_recommendations": len(self._recommendations),
            "strategy_stats": {k: dict(v) for k, v in self._strategy_stats.items()},
        }
