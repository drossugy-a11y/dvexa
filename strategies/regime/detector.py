"""市场状态检测器"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from data.market.akshare_feed import AkshareFeed


class RegimeDetector:
    """市场状态检测器"""
    
    def __init__(self):
        self.data_feed = AkshareFeed()
    
    def detect(self) -> str:
        """检测当前市场状态
        
        Returns:
            'bull' / 'bear' / 'shock'
        """
        try:
            # 获取沪深300指数数据
            index_data = self.data_feed.get_index_data('000300')
            
            if not index_data or len(index_data) < 60:
                return 'shock'  # 默认震荡
            
            close = [d['close'] for d in index_data]
            
            # 计算均线
            ma20 = sum(close[-20:]) / 20
            ma60 = sum(close[-60:]) / 60
            current = close[-1]
            
            # 判断逻辑
            if current > ma60 and current > ma20:
                return 'bull'  # 牛市
            elif current < ma60 and current < ma20:
                return 'bear'  # 熊市
            else:
                return 'shock'  # 震荡市
                
        except Exception as e:
            print(f"市场状态检测失败: {e}")
            return 'shock'
