"""Stock Data Tool — 基于 akshare 的 A 股数据获取

功能：
  - 获取股票列表（可按行业筛选）
  - 获取关键财务指标
  - 获取估值数据及历史分位数
  - 获取同行业公司列表
  - 获取股票基本信息

注意：akshare 接口有频率限制，每次请求间隔至少 0.5 秒。
"""

from __future__ import annotations

import time
from typing import Any


class StockDataTool:
    """A 股数据获取工具（基于 akshare）。"""

    def __init__(self, cache=None):
        self._cache = cache
        self._last_request_time = 0.0

    def call(self, input_data) -> dict:
        if isinstance(input_data, str):
            input_data = {"action": "info", "stock_code": input_data}
        action = input_data.get("action", "info")
        stock_code = input_data.get("stock_code", "")

        if action == "list":
            return self.get_stock_list(input_data.get("industry"))
        elif action == "info":
            return self.get_stock_info(stock_code)
        elif action == "financial":
            return self.get_financial_indicators(stock_code, input_data.get("years", 5))
        elif action == "valuation":
            return self.get_valuation_data(stock_code)
        elif action == "peers":
            return self.get_industry_peers(stock_code)
        return {"error": f"unknown action: {action}"}

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        self._last_request_time = time.time()

    def get_stock_list(self, industry: str = None) -> dict:
        self._rate_limit()
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if industry:
                df = df[df["名称"].str.contains(industry, na=False)]
            stocks = df[["代码", "名称", "最新价", "涨跌幅", "总市值", "市盈率-动态"]].head(100)
            return {
                "stocks": stocks.to_dict("records"),
                "total": len(stocks),
            }
        except Exception as e:
            return {"error": str(e), "stocks": []}

    def get_stock_info(self, stock_code: str) -> dict:
        cache_key = f"info_{stock_code}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        self._rate_limit()
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=stock_code)
            info = {}
            for _, row in df.iterrows():
                info[row.iloc[0]] = row.iloc[1]
            result = {
                "stock_code": stock_code,
                "name": info.get("股票简称", ""),
                "industry": info.get("行业", ""),
                "market_cap": info.get("总市值", ""),
                "list_date": info.get("上市时间", ""),
            }
            if self._cache:
                self._cache.set(cache_key, result)
            return result
        except Exception as e:
            return {"stock_code": stock_code, "error": str(e)}

    def get_financial_indicators(self, stock_code: str, years: int = 5) -> dict:
        cache_key = f"fin_{stock_code}_{years}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        self._rate_limit()
        try:
            import akshare as ak
            df = ak.stock_financial_analysis_indicator(symbol=stock_code)
            if df is None or df.empty:
                return {"stock_code": stock_code, "error": "no data"}

            result = {
                "stock_code": stock_code,
                "indicators": {},
            }
            key_cols = {
                "摊薄每股收益(元)": "eps",
                "每股净资产_调整后(元)": "bvps",
                "净资产收益率_加权(%)": "roe",
                "主营业务利润率(%)": "gross_margin",
                "净利润增长率(%)": "net_profit_growth",
                "主营业务收入增长率(%)": "revenue_growth",
                "资产负债比率(%)": "debt_ratio",
                "流动比率": "current_ratio",
                "每股经营性现金流(元)": "cash_flow_per_share",
            }
            for cn, en in key_cols.items():
                if cn in df.columns:
                    result["indicators"][en] = df[cn].head(years).tolist()

            if self._cache:
                self._cache.set(cache_key, result)
            return result
        except Exception as e:
            return {"stock_code": stock_code, "error": str(e)}

    def get_valuation_data(self, stock_code: str) -> dict:
        self._rate_limit()
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == stock_code]
            if row.empty:
                return {"stock_code": stock_code, "error": "not found"}

            current_pe = row.iloc[0].get("市盈率-动态", None)
            current_pb = row.iloc[0].get("市净率", None)

            return {
                "stock_code": stock_code,
                "current_pe": float(current_pe) if current_pe else None,
                "current_pb": float(current_pb) if current_pb else None,
            }
        except Exception as e:
            return {"stock_code": stock_code, "error": str(e)}

    def get_industry_peers(self, stock_code: str) -> dict:
        self._rate_limit()
        try:
            import akshare as ak
            info = self.get_stock_info(stock_code)
            industry = info.get("industry", "")
            if not industry:
                return {"stock_code": stock_code, "peers": [], "error": "no industry info"}

            df = ak.stock_zh_a_spot_em()
            df_industry = ak.stock_board_industry_cons_em(symbol=industry)
            if df_industry is None or df_industry.empty:
                return {"stock_code": stock_code, "industry": industry, "peers": []}

            peers = df_industry[["代码", "名称"]].head(10)
            return {
                "stock_code": stock_code,
                "industry": industry,
                "peers": peers.to_dict("records"),
            }
        except Exception as e:
            return {"stock_code": stock_code, "error": str(e)}
