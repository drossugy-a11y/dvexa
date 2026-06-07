"""Stock Recommendation Scorer — 推荐效果评估

功能：
  - 记录推荐时的价格和评分
  - 对比推荐前后的价格变化
  - 计算各策略的准确率
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class RecommendationRecord:
    """一次推荐记录。"""
    stock_code: str
    score: float
    strategy: str
    action: str
    price_at_recommendation: float
    ai_conclusion: dict = field(default_factory=dict)


class StockScorer:
    """推荐效果评估器。"""

    def __init__(self):
        self._records: list[RecommendationRecord] = []

    def record(self, stock_code: str, score: float, strategy: str,
               action: str, price: float, conclusion: dict = None):
        self._records.append(RecommendationRecord(
            stock_code=stock_code, score=score, strategy=strategy,
            action=action, price_at_recommendation=price,
            ai_conclusion=conclusion or {},
        ))

    def evaluate(self, stock_code: str, current_price: float,
                 days_later: int = 30) -> dict:
        recs = [r for r in self._records if r.stock_code == stock_code]
        if not recs:
            return {"error": "no record found"}

        latest = recs[-1]
        price_change = 0.0
        if latest.price_at_recommendation > 0:
            price_change = (current_price - latest.price_at_recommendation) / latest.price_at_recommendation * 100

        return {
            "stock_code": stock_code,
            "days_later": days_later,
            "recommendation_price": latest.price_at_recommendation,
            "current_price": current_price,
            "price_change_pct": round(price_change, 2),
            "score": latest.score,
            "action": latest.action,
            "strategy": latest.strategy,
        }

    def get_strategy_performance(self, strategy: str = "") -> dict:
        if strategy:
            recs = [r for r in self._records if r.strategy == strategy]
        else:
            recs = self._records

        if not recs:
            return {"total": 0}

        scores = [r.score for r in recs]
        actions = {}
        for r in recs:
            actions[r.action] = actions.get(r.action, 0) + 1

        return {
            "total": len(recs),
            "avg_score": round(sum(scores) / len(scores), 2),
            "action_distribution": actions,
        }

    def get_all_records(self) -> list[dict]:
        return [
            {
                "stock_code": r.stock_code,
                "score": r.score,
                "strategy": r.strategy,
                "action": r.action,
                "price": r.price_at_recommendation,
            }
            for r in self._records
        ]
