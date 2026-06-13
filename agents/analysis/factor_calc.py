"""因子计算器 - 基本面 + 技术面 + 估值"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from config.settings import (
    WEIGHT_GROWTH, WEIGHT_PROFITABILITY, WEIGHT_VALUATION,
    WEIGHT_HEALTH, WEIGHT_QUALITY
)


class FactorCalculator:
    """因子计算器"""

    def calculate(self, financial_data: dict, market_data: dict = None) -> dict:
        """计算因子

        Args:
            financial_data: {'indicators': {...}}  # 财务数据
            market_data: {
                'close_prices': list[float],  # 近60日收盘价
                'volumes': list[float],       # 近60日成交量
                'current_price': float,
                'pe': float,
                'pb': float,
                'dividend_yield': float,
            }

        Returns:
            {
                'fundamental': { growth, profitability, valuation, health, quality },
                'technical': { momentum_20d, momentum_60d, ma_trend, volume_trend, rsi_score },
                'valuation_scores': { pe_score, pb_score, dividend_yield },
                'total_score': float,
            }
        """
        indicators = financial_data.get('indicators', {})
        md = market_data or {}

        # 基本面五维评分
        fundamental = {
            'growth': self._score_growth(indicators),
            'profitability': self._score_profitability(indicators),
            'valuation': self._score_valuation(indicators),
            'health': self._score_health(indicators),
            'quality': self._score_quality(indicators),
        }

        # 技术因子
        technical = {
            'momentum_20d': self._score_momentum_20d(md.get('close_prices', [])),
            'momentum_60d': self._score_momentum_60d(md.get('close_prices', [])),
            'ma_trend': self._score_ma_trend(md.get('close_prices', [])),
            'volume_trend': self._score_volume_trend(md.get('volumes', [])),
            'rsi_score': self._score_rsi(md.get('close_prices', [])),
        }

        # 估值因子
        valuation_scores = {
            'pe_score': self._score_pe(md.get('pe')),
            'pb_score': self._score_pb(md.get('pb')),
            'dividend_yield': self._score_dividend_yield(md.get('dividend_yield')),
        }

        # 加权总分
        total = (
            fundamental['growth'] * WEIGHT_GROWTH +
            fundamental['profitability'] * WEIGHT_PROFITABILITY +
            fundamental['valuation'] * WEIGHT_VALUATION +
            fundamental['health'] * WEIGHT_HEALTH +
            fundamental['quality'] * WEIGHT_QUALITY
        )

        return {
            'fundamental': fundamental,
            'technical': technical,
            'valuation_scores': valuation_scores,
            'total_score': round(total, 1),
        }

    # ── 基本面因子 ──────────────────────────────────────

    def _score_growth(self, ind: dict) -> float:
        """成长性评分"""
        score = 50.0
        rev = [self._safe_float(x) for x in ind.get('revenue_growth', [])[:3] if x is not None]
        if rev:
            avg = sum(rev) / len(rev)
            if avg > 20: score += 20
            elif avg > 10: score += 10
            elif avg < 0: score -= 15
        profit = [self._safe_float(x) for x in ind.get('net_profit_growth', [])[:3] if x is not None]
        if profit:
            avg = sum(profit) / len(profit)
            if avg > 25: score += 15
            elif avg < 0: score -= 15
        return max(0, min(100, score))

    def _score_profitability(self, ind: dict) -> float:
        """盈利能力评分"""
        score = 50.0
        roe = [self._safe_float(x) for x in ind.get('roe', [])[:3] if x is not None]
        if roe:
            if roe[0] > 20: score += 25
            elif roe[0] > 15: score += 15
            elif roe[0] < 8: score -= 15
            if len(roe) >= 3 and all(r > 15 for r in roe):
                score += 10
        gm = [self._safe_float(x) for x in ind.get('gross_margin', [])[:3] if x is not None]
        if gm:
            if gm[0] > 40: score += 15
            elif gm[0] > 25: score += 5
        return max(0, min(100, score))

    def _score_valuation(self, ind: dict) -> float:
        """估值评分（基本面数据）"""
        score = 50.0
        eps = [self._safe_float(x) for x in ind.get('eps', [])[:2] if x is not None]
        if len(eps) >= 2 and eps[1] != 0:
            growth = (eps[0] - eps[1]) / abs(eps[1]) * 100
            if growth > 20: score += 15
            elif growth < -20: score -= 15
        return max(0, min(100, score))

    def _score_health(self, ind: dict) -> float:
        """财务健康评分"""
        score = 50.0
        debt = [self._safe_float(x) for x in ind.get('debt_ratio', [])[:1] if x is not None]
        if debt:
            if debt[0] < 40: score += 20
            elif debt[0] < 60: score += 10
            elif debt[0] > 75: score -= 20
        cr = [self._safe_float(x) for x in ind.get('current_ratio', [])[:1] if x is not None]
        if cr:
            if cr[0] > 2: score += 10
            elif cr[0] < 1: score -= 15
        cf = [self._safe_float(x) for x in ind.get('cash_flow_per_share', [])[:1] if x is not None]
        if cf:
            if cf[0] > 0: score += 15
            else: score -= 10
        return max(0, min(100, score))

    def _score_quality(self, ind: dict) -> float:
        """质量评分（稳定性）"""
        score = 50.0
        gm = [self._safe_float(x) for x in ind.get('gross_margin', [])[:3] if x is not None]
        if len(gm) >= 3:
            avg = sum(gm) / len(gm)
            std = (sum((x - avg) ** 2 for x in gm) / len(gm)) ** 0.5
            if std < 3: score += 15
            elif std > 10: score -= 10
        roe = [self._safe_float(x) for x in ind.get('roe', [])[:3] if x is not None]
        if len(roe) >= 3:
            if all(r > 15 for r in roe): score += 20
            elif all(r > 10 for r in roe): score += 10
        return max(0, min(100, score))

    # ── 技术因子 ────────────────────────────────────────

    def _score_momentum_20d(self, prices: list) -> float:
        """20日动量评分"""
        if len(prices) < 20:
            return 50.0
        ret = (prices[-1] - prices[-20]) / prices[-20] * 100
        if ret > 20: return 90
        if ret > 10: return 70 + (ret - 10) * 2
        if ret > 0: return 50 + ret * 2
        if ret > -10: return 40 + ret
        return 30

    def _score_momentum_60d(self, prices: list) -> float:
        """60日动量评分"""
        if len(prices) < 60:
            return 50.0
        ret = (prices[-1] - prices[-60]) / prices[-60] * 100
        if ret > 30: return 90
        if ret > 15: return 70 + (ret - 15) * 1.33
        if ret > 0: return 50 + ret * 1.33
        if ret > -15: return 40 + ret
        return 30

    def _score_ma_trend(self, prices: list) -> float:
        """均线多头排列评分"""
        if len(prices) < 60:
            return 50.0
        score = 0
        ma5 = sum(prices[-5:]) / 5
        ma10 = sum(prices[-10:]) / 10
        ma20 = sum(prices[-20:]) / 20
        ma60 = sum(prices[-60:]) / 60
        if ma5 > ma10: score += 25
        if ma10 > ma20: score += 25
        if ma20 > ma60: score += 25
        if prices[-1] > ma5: score += 25
        return float(score)

    def _score_volume_trend(self, volumes: list) -> float:
        """量能趋势评分"""
        if len(volumes) < 20:
            return 50.0
        avg5 = sum(volumes[-5:]) / 5
        avg20 = sum(volumes[-20:]) / 20
        if avg20 == 0:
            return 50.0
        ratio = avg5 / avg20
        if ratio > 1.5: return 80
        if ratio > 1.0: return 60 + (ratio - 1.0) * 40
        return 40

    def _score_rsi(self, prices: list, period: int = 14) -> float:
        """RSI 评分"""
        if len(prices) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(-period, 0):
            diff = prices[i] - prices[i - 1]
            if diff > 0:
                gains.append(diff)
            else:
                losses.append(abs(diff))
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0.001
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        if 30 <= rsi <= 70: return 80
        if rsi > 70: return 40  # 超买
        return 40  # 超卖

    # ── 估值因子 ────────────────────────────────────────

    def _score_pe(self, pe) -> float:
        """PE 评分"""
        if pe is None:
            return 50.0
        pe = self._safe_float(pe)
        if pe <= 0: return 30  # 亏损
        if pe < 15: return 90
        if pe < 30: return 60
        if pe < 100: return 30
        return 10

    def _score_pb(self, pb) -> float:
        """PB 评分"""
        if pb is None:
            return 50.0
        pb = self._safe_float(pb)
        if pb <= 0: return 30
        if pb < 1.5: return 90
        if pb < 3: return 60
        return 30

    def _score_dividend_yield(self, dy) -> float:
        """股息率评分"""
        if dy is None:
            return 30.0
        dy = self._safe_float(dy)
        if dy > 5: return 90
        if dy > 3: return 70
        if dy > 1: return 50
        return 30

    # ── 工具方法 ────────────────────────────────────────

    def _safe_float(self, value, default=0.0) -> float:
        """安全转换为 float"""
        if value is None or value == '' or value == '-':
            return default
        try:
            v = float(value)
            return default if v != v else v
        except:
            return default
