"""策略执行引擎"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import yaml
from strategies.regime.detector import RegimeDetector


class StrategyEngine:
    """策略执行引擎"""
    
    def __init__(self):
        self.detector = RegimeDetector()
        self.strategies_dir = os.path.join(os.path.dirname(__file__), 'configs')
    
    def detect_regime(self) -> str:
        """检测市场状态"""
        return self.detector.detect()
    
    def load_strategy(self, regime: str) -> dict:
        """加载对应策略配置"""
        strategy_map = {
            'bull': 'aggressive.yaml',
            'shock': 'balanced.yaml',
            'bear': 'defensive.yaml'
        }
        
        config_file = strategy_map.get(regime, 'balanced.yaml')
        config_path = os.path.join(self.strategies_dir, config_file)
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        return self._default_strategy()
    
    def screen(self, stocks: list, strategy: dict) -> list:
        """按策略筛选股票"""
        filters = strategy.get('filters', {})
        min_score = strategy.get('output', {}).get('min_score', 70)
        top_n = strategy.get('output', {}).get('top_n', 10)
        
        filtered = []
        for stock in stocks:
            # 基本过滤
            if stock.get('total_score', 0) < min_score:
                continue
            
            # 策略特定过滤
            if not self._apply_filters(stock, filters):
                continue
            
            filtered.append(stock)
        
        # 按评分排序
        filtered.sort(key=lambda x: x.get('total_score', 0), reverse=True)
        return filtered[:top_n]
    
    def _apply_filters(self, stock: dict, filters: dict) -> bool:
        """应用策略过滤器"""
        # 基本面过滤
        if 'roe_min' in filters:
            if stock.get('roe', 0) < filters['roe_min']:
                return False
        
        if 'pe_max' in filters:
            if stock.get('pe', 999) > filters['pe_max']:
                return False
        
        return True
    
    def _default_strategy(self) -> dict:
        """默认策略"""
        return {
            'name': '默认均衡策略',
            'regime': 'shock',
            'filters': {'roe_min': 10},
            'output': {'top_n': 10, 'min_score': 60}
        }
