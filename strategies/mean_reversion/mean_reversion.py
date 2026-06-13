"""均值回归策略实现"""


class MeanReversionStrategy:
    """均值回归策略"""
    
    def screen(self, stocks: list, config: dict) -> list:
        """均值回归策略筛选"""
        rsi_threshold = config.get('rsi_max', 30)
        
        filtered = []
        for stock in stocks:
            rsi = stock.get('rsi', 50)
            if rsi <= rsi_threshold:  # 超卖
                filtered.append(stock)
        
        return filtered
