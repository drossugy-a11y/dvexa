"""市场状态检测器 - 多维度增强版"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from data.market.akshare_feed import AkshareFeed


class RegimeDetector:
    """市场状态检测器 - 4维度加权"""

    def __init__(self):
        self.data_feed = AkshareFeed()

    def detect(self) -> dict:
        """检测当前市场状态

        Returns:
            {
                'regime': 'bull' | 'bear' | 'shock',
                'score': float,  # 0-100 综合分
                'confidence': float,  # 置信度
                'details': {
                    'trend_score': float,
                    'momentum_score': float,
                    'volatility_score': float,
                    'sentiment_score': float,
                },
                'indicators': {
                    'ma20': float,
                    'ma60': float,
                    'current_price': float,
                    'volatility_20d': float,
                    'momentum_20d': float,
                }
            }
        """
        try:
            index_data = self.data_feed.get_index_data('000300')

            if not index_data or len(index_data) < 60:
                return self._default_result()

            close = [d['close'] for d in index_data]
            volumes = [d.get('volume', 0) for d in index_data]

            # 4 个维度评分
            trend_score = self._score_trend(close)
            momentum_score = self._score_momentum(close)
            volatility_score = self._score_volatility(close)
            sentiment_score = self._score_sentiment(volumes)

            # 加权综合分
            total = (
                trend_score * 0.40 +
                momentum_score * 0.30 +
                volatility_score * 0.15 +
                sentiment_score * 0.15
            )

            # 判定
            if total > 70:
                regime = 'bull'
            elif total < 30:
                regime = 'bear'
            else:
                regime = 'shock'

            # 置信度（各维度一致性）
            scores = [trend_score, momentum_score, volatility_score, sentiment_score]
            avg = sum(scores) / len(scores)
            std = (sum((s - avg) ** 2 for s in scores) / len(scores)) ** 0.5
            confidence = max(0, 1 - std / 50)

            ma20 = sum(close[-20:]) / 20
            ma60 = sum(close[-60:]) / 60

            return {
                'regime': regime,
                'score': round(total, 1),
                'confidence': round(confidence, 2),
                'details': {
                    'trend_score': round(trend_score, 1),
                    'momentum_score': round(momentum_score, 1),
                    'volatility_score': round(volatility_score, 1),
                    'sentiment_score': round(sentiment_score, 1),
                },
                'indicators': {
                    'ma20': round(ma20, 2),
                    'ma60': round(ma60, 2),
                    'current_price': close[-1],
                    'volatility_20d': round(self._calc_volatility(close[-20:]), 4),
                    'momentum_20d': round((close[-1] - close[-20]) / close[-20] * 100, 2),
                }
            }

        except Exception as e:
            print(f"市场状态检测失败: {e}")
            return self._default_result()

    def _score_trend(self, close: list) -> float:
        """趋势维度（40% 权重）"""
        ma20 = sum(close[-20:]) / 20
        ma60 = sum(close[-60:]) / 60
        current = close[-1]

        score = 50.0

        # MA20/MA60 关系
        if current > ma60 and current > ma20:
            score += 20
        elif current < ma60 and current < ma20:
            score -= 20

        # MA60 斜率
        ma60_prev = sum(close[-70:-10]) / 60 if len(close) >= 70 else ma60
        if ma60_prev > 0:
            slope = (ma60 - ma60_prev) / ma60_prev * 100
            if slope > 0.5: score += 15
            elif slope < -0.5: score -= 15

        # 偏离度
        deviation = (current - ma60) / ma60 * 100
        if abs(deviation) > 15:
            score -= 10  # 过热或过冷

        return max(0, min(100, score))

    def _score_momentum(self, close: list) -> float:
        """动量维度（30% 权重）"""
        if len(close) < 20:
            return 50.0

        ret_20d = (close[-1] - close[-20]) / close[-20] * 100

        if ret_20d > 10: return 80
        if ret_20d > 5: return 70
        if ret_20d > 0: return 60
        if ret_20d > -5: return 40
        return 20

    def _score_volatility(self, close: list) -> float:
        """波动维度（15% 权重）"""
        vol = self._calc_volatility(close[-20:])
        if vol < 0.15: return 70  # 低波动
        if vol < 0.30: return 55
        return 40  # 高波动

    def _score_sentiment(self, volumes: list) -> float:
        """情绪维度（15% 权重）"""
        if len(volumes) < 20:
            return 50.0

        avg5 = sum(volumes[-5:]) / 5
        avg20 = sum(volumes[-20:]) / 20

        if avg20 == 0:
            return 50.0

        ratio = avg5 / avg20
        if ratio > 1.3: return 70  # 放量
        if ratio > 1.0: return 55
        return 35  # 缩量

    def _calc_volatility(self, prices: list) -> float:
        """计算年化波动率"""
        if len(prices) < 2:
            return 0.0
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices)) if prices[i-1] != 0]
        if not returns:
            return 0.0
        avg = sum(returns) / len(returns)
        std = (sum((r - avg) ** 2 for r in returns) / len(returns)) ** 0.5
        return std * (252 ** 0.5)  # 年化

    def _default_result(self) -> dict:
        """默认结果（数据不足时）"""
        return {
            'regime': 'shock',
            'score': 50.0,
            'confidence': 0.0,
            'details': {
                'trend_score': 50.0,
                'momentum_score': 50.0,
                'volatility_score': 50.0,
                'sentiment_score': 50.0,
            },
            'indicators': {}
        }
