"""TradingAgents-CN Wrapper - 封装多智能体分析框架"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

# 添加 vendor 路径
VENDOR_PATH = os.path.join(os.path.dirname(__file__), '..', 'vendor', 'TradingAgents-CN')


class TradingAgentsWrapper:
    """TradingAgents-CN 封装器

    通过 wrapper 调用 TradingAgents-CN 的多智能体分析框架。
    如果 vendor/TradingAgents-CN 不存在，返回降级结果。
    """

    def __init__(self):
        self._available = False
        self._ta_module = None

        # 尝试导入 TradingAgents-CN
        if os.path.exists(VENDOR_PATH):
            try:
                sys.path.insert(0, os.path.abspath(VENDOR_PATH))
                from tradingagents.graph import TradingAgentsGraph
                self._ta_module = TradingAgentsGraph
                self._available = True
                logger.info("TradingAgents-CN 已加载")
            except ImportError as e:
                logger.warning(f"TradingAgents-CN 导入失败: {e}")
        else:
            logger.warning(f"TradingAgents-CN 目录不存在: {VENDOR_PATH}")

    def is_available(self) -> bool:
        """检查 wrapper 是否可用"""
        return self._available

    def analyze(self, ticker: str, market: str = 'A', depth: int = 3) -> dict:
        """调用 TradingAgents-CN 分析单只股票

        Args:
            ticker: 股票代码，如 '000001'、'600519'
            market: 'A' / 'HK' / 'US'
            depth: 分析深度 1-5

        Returns:
            {
                'ticker': str,
                'name': str,
                'decision': 'buy' | 'hold' | 'sell',
                'confidence': float,  # 0-1
                'risk_score': float,  # 0-100
                'analysis': {
                    'technical': str,
                    'fundamental': str,
                    'news': str,
                    'sentiment': str,
                },
                'debate': {
                    'bull_argument': str,
                    'bear_argument': str,
                    'verdict': str,
                },
                'raw_report': str,
            }
        """
        if not self._available:
            return self._fallback(ticker)

        try:
            # 调用 TradingAgents-CN
            graph = self._ta_module()
            result = graph.analyze(ticker)

            return {
                'ticker': ticker,
                'name': result.get('name', ticker),
                'decision': result.get('decision', 'hold'),
                'confidence': result.get('confidence', 0.5),
                'risk_score': result.get('risk_score', 50),
                'analysis': {
                    'technical': result.get('analysis', {}).get('technical', ''),
                    'fundamental': result.get('analysis', {}).get('fundamental', ''),
                    'news': result.get('analysis', {}).get('news', ''),
                    'sentiment': result.get('analysis', {}).get('sentiment', ''),
                },
                'debate': {
                    'bull_argument': result.get('debate', {}).get('bull_argument', ''),
                    'bear_argument': result.get('debate', {}).get('bear_argument', ''),
                    'verdict': result.get('debate', {}).get('verdict', ''),
                },
                'raw_report': result.get('raw_report', ''),
            }
        except Exception as e:
            logger.error(f"TradingAgents-CN 分析失败 {ticker}: {e}")
            return self._fallback(ticker, error=str(e))

    def _fallback(self, ticker: str, error: str = None) -> dict:
        """降级结果"""
        return {
            'ticker': ticker,
            'name': ticker,
            'decision': 'hold',
            'confidence': 0.0,
            'risk_score': 50,
            'analysis': {
                'technical': '分析不可用（TradingAgents-CN 未安装）',
                'fundamental': '分析不可用',
                'news': '分析不可用',
                'sentiment': '分析不可用',
            },
            'debate': {
                'bull_argument': '',
                'bear_argument': '',
                'verdict': 'neutral',
            },
            'raw_report': f'降级模式: {error or "TradingAgents-CN 未安装"}',
        }
