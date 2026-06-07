"""Industry Comparator — 行业对比分析

功能：
  - 该股票在行业中的排名
  - 相对估值（和行业均值比）
"""

from __future__ import annotations


class IndustryComparator:
    def __init__(self, stock_data_tool=None, financial_tool=None):
        self._stock_data = stock_data_tool
        self._financial = financial_tool

    def call(self, input_data) -> dict:
        if isinstance(input_data, str):
            input_data = {"action": "ranking", "stock_code": input_data}
        action = input_data.get("action", "ranking")
        stock_code = input_data.get("stock_code", "")

        if action == "ranking":
            return self.get_industry_ranking(stock_code)
        elif action == "valuation":
            return self.get_relative_valuation(stock_code)
        return {"error": f"unknown action: {action}"}

    def get_industry_ranking(self, stock_code: str) -> dict:
        if not self._stock_data:
            return {"stock_code": stock_code, "error": "no data source"}

        peers_result = self._stock_data.get_industry_peers(stock_code)
        industry = peers_result.get("industry", "")
        peers = peers_result.get("peers", [])

        return {
            "stock_code": stock_code,
            "industry": industry,
            "peer_count": len(peers),
            "peers": peers[:10],
        }

    def get_relative_valuation(self, stock_code: str) -> dict:
        if not self._stock_data:
            return {"stock_code": stock_code, "error": "no data source"}

        valuation = self._stock_data.get_valuation_data(stock_code)
        peers_result = self._stock_data.get_industry_peers(stock_code)
        industry = peers_result.get("industry", "")

        return {
            "stock_code": stock_code,
            "industry": industry,
            "current_pe": valuation.get("current_pe"),
            "current_pb": valuation.get("current_pb"),
        }
