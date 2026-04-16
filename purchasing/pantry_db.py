import json
import sqlite3


class PantryDB:
    def __init__(self, db_path: str):
        self._path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self._path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pantry (
                    ingredient_name   TEXT PRIMARY KEY,
                    asin              TEXT NOT NULL,
                    product_title     TEXT,
                    store             TEXT DEFAULT 'WholeFoods',
                    last_used         DATE,
                    confirmed_by_user INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_review (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    ingredient_name  TEXT,
                    candidates       TEXT,
                    week             TEXT
                )
            """)

    def _normalize(self, name: str) -> str:
        return name.strip().lower()

    def get(self, ingredient_name: str) -> dict | None:
        key = self._normalize(ingredient_name)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT asin, product_title, confirmed_by_user FROM pantry WHERE ingredient_name = ?",
                (key,)
            ).fetchone()
        if row is None:
            return None
        return {"asin": row[0], "product_title": row[1], "confirmed_by_user": bool(row[2])}

    def save(self, ingredient_name: str, asin: str, product_title: str, confirmed_by_user: bool = False):
        key = self._normalize(ingredient_name)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO pantry (ingredient_name, asin, product_title, confirmed_by_user, last_used)
                   VALUES (?, ?, ?, ?, DATE('now'))
                   ON CONFLICT(ingredient_name) DO UPDATE SET
                     asin = excluded.asin,
                     product_title = excluded.product_title,
                     confirmed_by_user = excluded.confirmed_by_user,
                     last_used = excluded.last_used""",
                (key, asin, product_title, int(confirmed_by_user))
            )

    def add_pending(self, ingredient_name: str, candidates: list[dict], week: str):
        key = self._normalize(ingredient_name)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pending_review (ingredient_name, candidates, week) VALUES (?, ?, ?)",
                (key, json.dumps(candidates), week)
            )

    def get_pending(self, week: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ingredient_name, candidates FROM pending_review WHERE week = ?",
                (week,)
            ).fetchall()
        return [{"ingredient_name": r[0], "candidates": json.loads(r[1])} for r in rows]

    def clear_pending(self, week: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM pending_review WHERE week = ?", (week,))
