"""搜索记录存储(SQLite)。失败的请求不保存。

记录字段:(id, source, result, mode, ts),mode ∈ {translate, explain}。
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import List, Optional


class HistoryStore:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                result TEXT NOT NULL,
                mode TEXT NOT NULL,
                ts REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def add(self, source: str, result: str, mode: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO records (source, result, mode, ts) VALUES (?, ?, ?, ?)",
            (source, result, mode, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid

    def search(
        self, query: str = "", mode: Optional[str] = None, limit: int = 1000
    ) -> List[dict]:
        sql = "SELECT id, source, result, mode, ts FROM records"
        conds: List[str] = []
        params: List[object] = []
        if query:
            conds.append("(source LIKE ? OR result LIKE ?)")
            like = f"%{query}%"
            params += [like, like]
        if mode:
            conds.append("mode = ?")
            params.append(mode)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def delete(self, ids: List[int]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self._conn.execute(f"DELETE FROM records WHERE id IN ({placeholders})", ids)
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM records")
        self._conn.commit()

    def export_json(self, path: str) -> None:
        rows = self.search(limit=10_000)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    def close(self) -> None:
        self._conn.close()
