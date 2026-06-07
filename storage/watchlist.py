"""自选股管理。"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime


class Watchlist:
    def __init__(self, db_path: str = "data/stock.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_table()

    def _init_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                code TEXT PRIMARY KEY,
                tag TEXT DEFAULT '待观察',
                note TEXT DEFAULT '',
                added_at TEXT,
                updated_at TEXT
            )
        """)
        self._conn.commit()

    def add(self, stock_code: str, tag: str = "待观察", note: str = ""):
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO watchlist VALUES (?, ?, ?, ?, ?)",
            (stock_code, tag, note, now, now),
        )
        self._conn.commit()

    def remove(self, stock_code: str):
        self._conn.execute("DELETE FROM watchlist WHERE code=?", (stock_code,))
        self._conn.commit()

    def update_tag(self, stock_code: str, tag: str):
        self._conn.execute(
            "UPDATE watchlist SET tag=?, updated_at=? WHERE code=?",
            (tag, datetime.now().isoformat(), stock_code),
        )
        self._conn.commit()

    def add_note(self, stock_code: str, note: str):
        self._conn.execute(
            "UPDATE watchlist SET note=?, updated_at=? WHERE code=?",
            (note, datetime.now().isoformat(), stock_code),
        )
        self._conn.commit()

    def list_all(self, tag: str = None) -> list[dict]:
        if tag:
            rows = self._conn.execute(
                "SELECT * FROM watchlist WHERE tag=? ORDER BY updated_at DESC", (tag,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM watchlist ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def contains(self, stock_code: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM watchlist WHERE code=?", (stock_code,)
        ).fetchone()
        return row is not None

    def close(self):
        self._conn.close()
