"""Stock Screener — 条件筛选器

从 SQLite 数据库中按条件筛选股票。
"""

from __future__ import annotations


class StockScreener:
    def __init__(self, stock_data_tool=None, db=None):
        self._stock_data = stock_data_tool
        self._db = db

    def call(self, input_data) -> dict:
        if isinstance(input_data, str):
            input_data = {"conditions": {"keyword": input_data}}
        conditions = input_data.get("conditions", input_data)
        return self.screen(conditions)

    def screen(self, conditions: dict) -> dict:
        if self._stock_data:
            return self._screen_from_api(conditions)
        if self._db:
            return self._screen_from_db(conditions)
        return {"error": "no data source", "codes": []}

    def _screen_from_api(self, conditions: dict) -> dict:
        result = self._stock_data.get_stock_list(conditions.get("industry"))
        stocks = result.get("stocks", [])

        filtered = []
        pe_max = conditions.get("pe_max", 999)
        pe_min = conditions.get("pe_min", 0)
        market_cap_min = conditions.get("market_cap_min", 0)

        for s in stocks:
            pe = s.get("市盈率-动态")
            if pe is None:
                continue
            try:
                pe_val = float(pe)
            except (ValueError, TypeError):
                continue
            if pe_val < pe_min or pe_val > pe_max:
                continue
            if market_cap_min:
                mc = s.get("总市值", 0)
                try:
                    if float(mc) < market_cap_min * 1e8:
                        continue
                except (ValueError, TypeError):
                    continue
            filtered.append(s)

        codes = [s.get("代码", "") for s in filtered]
        return {"codes": codes, "total": len(codes), "conditions": conditions}

    def _screen_from_db(self, conditions: dict) -> dict:
        if not self._db:
            return {"codes": [], "error": "no db"}
        try:
            return self._db.query_stocks(conditions)
        except Exception as e:
            return {"codes": [], "error": str(e)}
