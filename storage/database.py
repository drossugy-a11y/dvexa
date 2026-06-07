"""SQLite 数据库存储。

表：
  - stocks: 股票基本信息
  - financial_data: 财务指标历史
  - analysis_results: AI 分析结果
  - screening_history: 筛选历史
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime


class StockDatabase:
    def __init__(self, db_path: str = "data/stock.db"):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        c = self._conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                industry TEXT,
                market_cap REAL,
                list_date TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS financial_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                year TEXT,
                indicator TEXT,
                value REAL,
                updated_at TEXT,
                UNIQUE(code, year, indicator)
            );
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                strategy TEXT,
                score REAL,
                conclusion TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS screening_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conditions TEXT,
                result_codes TEXT,
                result_count INTEGER,
                created_at TEXT
            );
        """)
        self._conn.commit()

    def save_stock(self, code: str, name: str, industry: str = "",
                   market_cap: float = 0, list_date: str = ""):
        self._conn.execute(
            "INSERT OR REPLACE INTO stocks VALUES (?, ?, ?, ?, ?, ?)",
            (code, name, industry, market_cap, list_date, datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_stock(self, code: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM stocks WHERE code=?", (code,)).fetchone()
        return dict(row) if row else None

    def save_financial_data(self, code: str, year: str, indicator: str, value: float):
        self._conn.execute(
            "INSERT OR REPLACE INTO financial_data VALUES (NULL, ?, ?, ?, ?, ?)",
            (code, year, indicator, value, datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_financial_data(self, code: str) -> dict:
        rows = self._conn.execute(
            "SELECT indicator, value, year FROM financial_data WHERE code=? ORDER BY year DESC",
            (code,),
        ).fetchall()
        result = {}
        for row in rows:
            ind = row["indicator"]
            if ind not in result:
                result[ind] = []
            result[ind].append(row["value"])
        return {"stock_code": code, "indicators": result}

    def save_analysis(self, code: str, strategy: str, score: float, conclusion: dict):
        self._conn.execute(
            "INSERT INTO analysis_results VALUES (NULL, ?, ?, ?, ?, ?)",
            (code, strategy, score, json.dumps(conclusion, ensure_ascii=False),
             datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_analysis_history(self, code: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM analysis_results WHERE code=? ORDER BY created_at DESC",
            (code,),
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["conclusion"] = json.loads(d["conclusion"]) if d["conclusion"] else {}
            result.append(d)
        return result

    def save_screening(self, conditions: dict, result_codes: list):
        self._conn.execute(
            "INSERT INTO screening_history VALUES (NULL, ?, ?, ?, ?)",
            (json.dumps(conditions, ensure_ascii=False),
             json.dumps(result_codes), len(result_codes),
             datetime.now().isoformat()),
        )
        self._conn.commit()

    def query_stocks(self, conditions: dict) -> dict:
        query = "SELECT code FROM stocks WHERE 1=1"
        params = []
        if conditions.get("industry"):
            query += " AND industry=?"
            params.append(conditions["industry"])
        if conditions.get("market_cap_min"):
            query += " AND market_cap>=?"
            params.append(conditions["market_cap_min"] * 1e8)
        rows = self._conn.execute(query, params).fetchall()
        return {"codes": [r["code"] for r in rows]}

    def close(self):
        self._conn.close()
