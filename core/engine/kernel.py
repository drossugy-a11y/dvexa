"""主控制循环 - 协调所有模块"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from data.market.akshare_feed import AkshareFeed
from agents.analysis.factor_calc import FactorCalculator
from strategies.engine import StrategyEngine
from agents.research.analyzer import ResearchAnalyzer


class Kernel:
    """主控制循环"""
    
    def __init__(self):
        self.data_feed = AkshareFeed()
        self.factor_calc = FactorCalculator()
        self.strategy_engine = StrategyEngine()
        self.researcher = ResearchAnalyzer()
    
    def run(self, config_path: str = None):
        """执行完整选股流程"""
        # 1. 判断市场状态
        regime = self.strategy_engine.detect_regime()
        
        # 2. 加载对应策略
        strategy = self.strategy_engine.load_strategy(regime)
        
        # 3. 获取股票数据
        stocks = self.data_feed.get_stock_list()
        
        # 4. 计算因子
        scored_stocks = []
        for stock in stocks[:100]:  # 限制数量
            factors = self.factor_calc.calculate(stock)
            scored_stocks.append({**stock, **factors})
        
        # 5. 策略筛选
        candidates = self.strategy_engine.screen(scored_stocks, strategy)
        
        # 6. 研究分析
        reports = []
        for stock in candidates[:10]:  # Top 10
            report = self.researcher.analyze(stock)
            reports.append(report)
        
        return {
            'regime': regime,
            'strategy': strategy['name'],
            'candidates': candidates,
            'reports': reports
        }
