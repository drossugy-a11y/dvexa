"""Tests for storage modules."""

import os
import tempfile

from storage.database import StockDatabase
from storage.watchlist import Watchlist
from storage.event_store import StockEventStore


class TestStockDatabase:
    def setup_method(self):
        self.tmp = tempfile.mktemp(suffix=".db")
        self.db = StockDatabase(self.tmp)

    def teardown_method(self):
        self.db.close()
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_save_and_get_stock(self):
        self.db.save_stock("600519", "贵州茅台", "白酒", 20000e8, "2001-08-27")
        stock = self.db.get_stock("600519")
        assert stock is not None
        assert stock["name"] == "贵州茅台"
        assert stock["industry"] == "白酒"

    def test_save_financial_data(self):
        self.db.save_financial_data("600519", "2023", "roe", 30.0)
        self.db.save_financial_data("600519", "2022", "roe", 28.0)
        data = self.db.get_financial_data("600519")
        assert "roe" in data["indicators"]
        assert len(data["indicators"]["roe"]) == 2

    def test_save_analysis(self):
        self.db.save_analysis("600519", "value", 8.5, {"summary": "test"})
        history = self.db.get_analysis_history("600519")
        assert len(history) == 1
        assert history[0]["score"] == 8.5

    def test_save_screening(self):
        self.db.save_stock("600519", "茅台", "白酒")
        self.db.save_stock("000858", "五粮液", "白酒")
        self.db.save_screening({"industry": "白酒"}, ["600519", "000858"])


class TestWatchlist:
    def setup_method(self):
        self.tmp = tempfile.mktemp(suffix=".db")
        self.wl = Watchlist(self.tmp)

    def teardown_method(self):
        self.wl.close()
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_add_and_list(self):
        self.wl.add("600519", tag="待观察", note="关注")
        stocks = self.wl.list_all()
        assert len(stocks) == 1
        assert stocks[0]["code"] == "600519"

    def test_update_tag(self):
        self.wl.add("600519")
        self.wl.update_tag("600519", "已研究")
        stocks = self.wl.list_all()
        assert stocks[0]["tag"] == "已研究"

    def test_remove(self):
        self.wl.add("600519")
        self.wl.remove("600519")
        assert len(self.wl.list_all()) == 0

    def test_filter_by_tag(self):
        self.wl.add("600519", tag="已研究")
        self.wl.add("000858", tag="待观察")
        assert len(self.wl.list_all("已研究")) == 1
        assert len(self.wl.list_all("待观察")) == 1

    def test_contains(self):
        self.wl.add("600519")
        assert self.wl.contains("600519") is True
        assert self.wl.contains("000858") is False


class TestStockEventStore:
    def setup_method(self):
        self.tmp = tempfile.mktemp(suffix=".jsonl")
        self.store = StockEventStore(self.tmp)

    def teardown_method(self):
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_append_and_query(self):
        self.store.append({"event_type": "analysis", "stock_code": "600519", "data": {}})
        assert self.store.count == 1
        events = self.store.query_by_stock("600519")
        assert len(events) == 1

    def test_persistence(self):
        self.store.append({"event_type": "screening", "data": {"count": 10}})
        store2 = StockEventStore(self.tmp)
        assert store2.count == 1

    def test_query_by_type(self):
        self.store.append({"event_type": "analysis", "data": {}})
        self.store.append({"event_type": "screening", "data": {}})
        assert len(self.store.query_by_type("analysis")) == 1
        assert len(self.store.query_by_type("screening")) == 1
