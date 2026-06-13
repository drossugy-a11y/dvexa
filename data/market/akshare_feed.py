"""akshare 数据源"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import time
from datetime import datetime, timedelta
from config.settings import REQUEST_INTERVAL, CACHE_EXPIRE_HOURS


class AkshareFeed:
    """akshare A 股数据源"""
    
    def __init__(self):
        self._last_request = 0.0
        self._cache = {}
    
    def _rate_limit(self):
        """请求限流"""
        elapsed = time.time() - self._last_request
        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)
        self._last_request = time.time()
    
    def get_stock_list(self, industry: str = None) -> list:
        """获取股票列表"""
        cache_key = f"stock_list_{industry or 'all'}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        self._rate_limit()
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            
            if industry:
                df = df[df['名称'].str.contains(industry, na=False)]
            
            cols = ['代码', '名称', '最新价', '涨跌幅', '总市值', '市盈率-动态', '市净率', '换手率']
            for c in cols:
                if c not in df.columns:
                    df[c] = None
            
            stocks = df[cols].head(5000).to_dict('records')
            self._cache[cache_key] = stocks
            return stocks
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return []
    
    def get_financial_indicators(self, stock_code: str, years: int = 5) -> dict:
        """获取财务指标"""
        cache_key = f"fin_{stock_code}_{years}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        self._rate_limit()
        try:
            import akshare as ak
            df = ak.stock_financial_analysis_indicator(symbol=stock_code)
            
            if df is None or df.empty:
                return {'stock_code': stock_code, 'indicators': {}, 'error': 'no data'}
            
            key_cols = {
                '摊薄每股收益(元)': 'eps',
                '每股净资产_调整后(元)': 'bvps',
                '净资产收益率_加权(%)': 'roe',
                '主营业务利润率(%)': 'gross_margin',
                '净利润增长率(%)': 'net_profit_growth',
                '主营业务收入增长率(%)': 'revenue_growth',
                '资产负债比率(%)': 'debt_ratio',
                '流动比率': 'current_ratio',
                '每股经营性现金流(元)': 'cash_flow_per_share',
            }
            
            indicators = {}
            for cn, en in key_cols.items():
                if cn in df.columns:
                    indicators[en] = df[cn].head(years).tolist()
            
            result = {'stock_code': stock_code, 'indicators': indicators}
            self._cache[cache_key] = result
            return result
        except Exception as e:
            print(f"获取财务指标失败 {stock_code}: {e}")
            return {'stock_code': stock_code, 'indicators': {}, 'error': str(e)}
    
    def get_index_data(self, index_code: str) -> list:
        """获取指数数据"""
        self._rate_limit()
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
            
            if df is None or len(df) < 60:
                return []
            
            data = []
            for _, row in df.tail(120).iterrows():
                data.append({
                    'date': str(row.get('date', '')),
                    'close': float(row.get('close', 0)),
                    'volume': float(row.get('volume', 0))
                })
            return data
        except Exception as e:
            print(f"获取指数数据失败: {e}")
            return []
    
    def get_stock_info(self, stock_code: str) -> dict:
        """获取股票基础信息"""
        self._rate_limit()
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=stock_code)
            info = {}
            for _, row in df.iterrows():
                info[str(row.iloc[0])] = row.iloc[1]
            return {
                'stock_code': stock_code,
                'name': info.get('股票简称', ''),
                'industry': info.get('行业', ''),
                'market_cap': info.get('总市值', ''),
            }
        except Exception as e:
            return {'stock_code': stock_code, 'error': str(e)}
