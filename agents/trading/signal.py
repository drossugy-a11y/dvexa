"""交易信号生成（Phase 2）"""


class TradingSignal:
    """交易信号生成器"""
    
    def generate(self, stock: dict, analysis: dict) -> dict:
        """生成交易信号"""
        return {
            'action': 'hold',  # buy/sell/hold
            'confidence': 0.0,
            'reason': '待实现'
        }
