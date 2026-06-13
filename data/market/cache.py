"""SQLite 缓存层"""

import sqlite3
import json
import os
from datetime import datetime, timedelta


class SQLiteCache:
    """SQLite 本地缓存"""
    
    def __init__(self, db_path: str = 'cache.db'):
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        ''')
        self._conn.commit()
    
    def get(self, key: str, expire_hours: int = 24) -> dict | None:
        """获取缓存"""
        row = self._conn.execute(
            'SELECT value, updated_at FROM cache WHERE key=?', (key,)
        ).fetchone()
        
        if not row:
            return None
        
        updated = datetime.fromisoformat(row[1])
        if datetime.now() - updated > timedelta(hours=expire_hours):
            self._conn.execute('DELETE FROM cache WHERE key=?', (key,))
            self._conn.commit()
            return None
        
        try:
            return json.loads(row[0])
        except:
            return None
    
    def set(self, key: str, value: dict):
        """设置缓存"""
        self._conn.execute(
            'INSERT OR REPLACE INTO cache VALUES (?, ?, ?)',
            (key, json.dumps(value, ensure_ascii=False, default=str),
             datetime.now().isoformat())
        )
        self._conn.commit()
    
    def close(self):
        """关闭连接"""
        self._conn.close()
