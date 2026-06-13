"""策略切换器"""


class StrategySwitcher:
    """根据市场状态切换策略"""
    
    STRATEGIES = {
        'bull': 'aggressive.yaml',
        'shock': 'balanced.yaml',
        'bear': 'defensive.yaml'
    }
    
    def get_config_file(self, regime: str) -> str:
        """获取策略配置文件名"""
        return self.STRATEGIES.get(regime, 'balanced.yaml')
