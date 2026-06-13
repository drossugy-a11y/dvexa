"""记忆模块 - SQLite 持久化"""

import sqlite3
import json
import os
from datetime import datetime


class AnalysisMemory:
    """分析记忆 - 缓存分析结果、记录扫描历史"""

    def __init__(self, db_path: str = 'data/dvexa_memory.db'):
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS analysis_cache (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, date)
            );

            CREATE TABLE IF NOT EXISTS scan_history (
                scan_id TEXT PRIMARY KEY,
                regime TEXT,
                strategy_name TEXT,
                candidates_json TEXT,
                decisions_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS regime_history (
                date TEXT PRIMARY KEY,
                regime TEXT,
                score REAL,
                details_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trade_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id TEXT,
                ticker TEXT,
                action TEXT,
                confirmed BOOLEAN DEFAULT FALSE,
                confirmed_at TIMESTAMP,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    def get_cached_analysis(self, ticker: str) -> dict | None:
        """获取今日缓存"""
        today = datetime.now().strftime('%Y-%m-%d')
        row = self._conn.execute(
            "SELECT result_json FROM analysis_cache WHERE ticker=? AND date=?",
            (ticker, today)
        ).fetchone()
        if row:
            try:
                return json.loads(row['result_json'])
            except:
                return None
        return None

    def cache_analysis(self, ticker: str, result: dict):
        """缓存分析结果"""
        today = datetime.now().strftime('%Y-%m-%d')
        self._conn.execute(
            "INSERT OR REPLACE INTO analysis_cache VALUES (?, ?, ?, ?)",
            (ticker, today, json.dumps(result, ensure_ascii=False, default=str), datetime.now().isoformat())
        )
        self._conn.commit()

    def save_scan(self, scan_id: str, result: dict):
        """保存扫描结果"""
        self._conn.execute(
            "INSERT OR REPLACE INTO scan_history VALUES (?, ?, ?, ?, ?, ?)",
            (scan_id, result.get('regime', ''), result.get('strategy_name', ''),
             json.dumps(result.get('candidates', []), ensure_ascii=False, default=str),
             json.dumps(result.get('decisions', []), ensure_ascii=False, default=str),
             datetime.now().isoformat())
        )
        self._conn.commit()

    def get_scan(self, scan_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM scan_history WHERE scan_id=?", (scan_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d['candidates'] = json.loads(d.get('candidates_json') or '[]')
            d['decisions'] = json.loads(d.get('decisions_json') or '[]')
            return d
        return None

    def get_recent_scans(self, limit: int = 10) -> list:
        rows = self._conn.execute(
            "SELECT scan_id, regime, strategy_name, created_at FROM scan_history ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def save_regime(self, date: str, regime: str, score: float, details: dict):
        self._conn.execute(
            "INSERT OR REPLACE INTO regime_history VALUES (?, ?, ?, ?, ?)",
            (date, regime, score, json.dumps(details, ensure_ascii=False, default=str), datetime.now().isoformat())
        )
        self._conn.commit()

    def get_regime_history(self, days: int = 30) -> list:
        rows = self._conn.execute(
            "SELECT * FROM regime_history ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in rows]

    def log_trade(self, scan_id: str, ticker: str, action: str):
        self._conn.execute(
            "INSERT INTO trade_log (scan_id, ticker, action) VALUES (?, ?, ?)",
            (scan_id, ticker, action)
        )
        self._conn.commit()

    def confirm_trade(self, ticker: str, scan_id: str):
        self._conn.execute(
            "UPDATE trade_log SET confirmed=TRUE, confirmed_at=? WHERE ticker=? AND scan_id=?",
            (datetime.now().isoformat(), ticker, scan_id)
        )
        self._conn.commit()
