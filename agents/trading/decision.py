"""交易决策 Agent - 规则 + LLM 辅助"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import logging
from dataclasses import dataclass
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)


@dataclass
class TradeDecision:
    ticker: str
    name: str
    action: str           # 'buy' | 'hold' | 'sell' | 'watch'
    confidence: float     # 0-1
    target_pct: float     # 建议仓位比例
    entry_price: float    # 建议入场价
    stop_loss: float      # 止损价
    take_profit: float    # 止盈价
    holding_weeks: int    # 建议持仓周数
    reason: str           # 决策理由
    risk_level: str       # 'low' | 'medium' | 'high'


class TradeDecisionMaker:
    """交易决策 Agent"""

    # 仓位限制
    POSITION_LIMITS = {
        'bull':  {'max_single': 0.15, 'max_total': 0.80},
        'shock': {'max_single': 0.08, 'max_total': 0.60},
        'bear':  {'max_single': 0.05, 'max_total': 0.30},
    }

    def decide(self, debate_result, regime: str, strategy_config: dict, stock_data: dict = None) -> TradeDecision:
        """生成交易决策

        Args:
            debate_result: DebateResult 或 dict
            regime: 'bull' / 'bear' / 'shock'
            strategy_config: 策略配置
            stock_data: 股票数据（含价格等）
        """
        if hasattr(debate_result, '__dict__'):
            dr = debate_result.__dict__
        else:
            dr = debate_result

        ticker = dr.get('ticker', '')
        verdict = dr.get('verdict', 'neutral')
        total_score = stock_data.get('total_score', 50) if stock_data else 50
        limits = self.POSITION_LIMITS.get(regime, self.POSITION_LIMITS['shock'])

        # 规则层决策
        action, confidence, reason = self._rule_based(verdict, total_score, regime)

        # 仓位计算
        target_pct = min(limits['max_single'], confidence * limits['max_single'])

        # 止损止盈
        entry = stock_data.get('current_price', 0) if stock_data else 0
        stop_loss = round(entry * 0.93, 2) if entry else 0   # -7%
        take_profit = round(entry * 1.20, 2) if entry else 0  # +20%

        # 风险等级
        risk_level = 'low' if confidence > 0.7 else 'medium' if confidence > 0.4 else 'high'

        return TradeDecision(
            ticker=ticker,
            name=stock_data.get('name', ticker) if stock_data else ticker,
            action=action,
            confidence=round(confidence, 2),
            target_pct=round(target_pct, 4),
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            holding_weeks=6 if action == 'buy' else 0,
            reason=reason,
            risk_level=risk_level,
        )

    def _rule_based(self, verdict: str, total_score: float, regime: str) -> tuple:
        """规则层决策"""
        if regime == 'bull':
            if verdict == 'bull_win' and total_score > 80:
                return 'buy', 0.85, '牛市+看涨胜+高分'
            if verdict == 'bull_win' and total_score > 65:
                return 'buy', 0.65, '牛市+看涨胜'
            if verdict == 'bear_win':
                return 'watch', 0.3, '牛市+看跌胜，观望'
            return 'hold', 0.5, '牛市+中性'

        elif regime == 'bear':
            if verdict == 'bear_win':
                return 'sell', 0.8, '熊市+看跌胜'
            if total_score < 50:
                return 'watch', 0.2, '熊市+低分，回避'
            return 'hold', 0.3, '熊市+中性，防守'

        else:  # shock
            if verdict == 'bull_win' and total_score > 70:
                return 'buy', 0.55, '震荡+看涨胜+高分'
            if verdict == 'bear_win':
                return 'watch', 0.3, '震荡+看跌胜'
            return 'hold', 0.4, '震荡+中性'

    def decide_batch(self, debate_results: list, regime: str, strategy_config: dict, stock_data_map: dict = None) -> list:
        """批量决策"""
        decisions = []
        for dr in debate_results:
            ticker = dr.get('ticker', '') if isinstance(dr, dict) else dr.ticker
            sd = (stock_data_map or {}).get(ticker, {})
            d = self.decide(dr, regime, strategy_config, sd)
            decisions.append(d)

        # 按 confidence 排序
        decisions.sort(key=lambda x: x.confidence, reverse=True)
        return decisions
