"""动量策略实现"""


class MomentumStrategy:
    """动量策略"""
    
    def screen(self, stocks: list, config: dict) -> list:
        """动量策略筛选"""
        min_return = config.get('min_return', 10)
        
        filtered = []
        for stock in stocks:
            momentum = stock.get('momentum', 0)
            if momentum >= min_return:
                filtered.append(stock)
        
        return filtered
