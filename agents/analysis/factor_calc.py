"""因子计算器 - 自行设计因子"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from config.settings import (
    WEIGHT_GROWTH, WEIGHT_PROFITABILITY, WEIGHT_VALUATION,
    WEIGHT_HEALTH, WEIGHT_QUALITY
)


class FactorCalculator:
    """因子计算器"""
    
    def calculate(self, financial_data: dict) -> dict:
        """计算五维因子 + 技术因子"""
        indicators = financial_data.get('indicators', {})
        
        # 基本面五维评分
        growth = self._score_growth(indicators)
        profitability = self._score_profitability(indicators)
        valuation = self._score_valuation(indicators)
        health = self._score_health(indicators)
        quality = self._score_quality(indicators)
        
        # 加权总分
        total = (
            growth * WEIGHT_GROWTH +
            profitability * WEIGHT_PROFITABILITY +
            valuation * WEIGHT_VALUATION +
            health * WEIGHT_HEALTH +
            quality * WEIGHT_QUALITY
        )
        
        return {
            'growth': growth,
            'profitability': profitability,
            'valuation': valuation,
            'health': health,
            'quality': quality,
            'total_score': round(total, 1)
        }
    
    def _score_growth(self, ind: dict) -> float:
        """成长性评分"""
        score = 50.0
        rev = [self._safe_float(x) for x in ind.get('revenue_growth', [])[:3] if x is not None]
        if rev:
            avg = sum(rev) / len(rev)
            if avg > 20: score += 20
            elif avg > 10: score += 10
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
        return max(0, min(100, score))
    
    def _score_valuation(self, ind: dict) -> float:
        """估值评分"""
        score = 50.0
        return max(0, min(100, score))
    
    def _score_health(self, ind: dict) -> float:
        """财务健康评分"""
        score = 50.0
        debt = [self._safe_float(x) for x in ind.get('debt_ratio', [])[:1] if x is not None]
        if debt:
            if debt[0] < 40: score += 20
            elif debt[0] > 75: score -= 20
        return max(0, min(100, score))
    
    def _score_quality(self, ind: dict) -> float:
        """质量评分"""
        score = 50.0
        return max(0, min(100, score))
    
    def _safe_float(self, value, default=0.0) -> float:
        """安全转换为 float"""
        if value is None or value == '' or value == '-':
            return default
        try:
            v = float(value)
            return default if v != v else v  # NaN check
        except:
            return default
