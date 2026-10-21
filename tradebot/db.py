"""SQLite kalıcılık katmanı. Her çağrı kendi bağlantısını açar; bu sayede worker thread'leri güvenle kullanabilir."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    strategy TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    quantity REAL NOT NULL,
    mode TEXT NOT NULL DEFAULT 'dry',
    poll_seconds INTEGER NOT NULL DEFAULT 60,
    status TEXT NOT NULL DEFAULT 'stopped',
    position_qty REAL NOT NULL DEFAULT 0,
    entry_price REAL,
    last_candle_time TEXT,
    last_run_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL,
    mode TEXT NOT NULL,
    reason TEXT,
    exchange_order_id TEXT,
    raw TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_bot ON orders(bot_id, id);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_bot ON logs(bot_id, id);
"""

BOT_FIELDS = ("name", "symbol", "interval", "strategy", "params", "quantity", "mode", "poll_seconds")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        with self._lock:
            c = sqlite3.connect(self.path, timeout=30)
            c.row_factory = sqlite3.Row
            try:
                yield c
                c.commit()
            finally:
                c.close()

    @staticmethod
    def _bot(row):
        if row is None:
            return None
        d = dict(row)
        d["params"] = json.loads(d["params"] or "{}")
        return d

    # --- bots ---
    def list_bots(self):
        with self.conn() as c:
            return [self._bot(r) for r in c.execute("SELECT * FROM bots ORDER BY id")]

    def get_bot(self, bot_id: int):
        with self.conn() as c:
            return self._bot(c.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone())

    def create_bot(self, data: dict) -> dict:
        values = {k: data[k] for k in BOT_FIELDS}
        values["params"] = json.dumps(values["params"])
        ts = now()
        with self.conn() as c:
            cur = c.execute(
                f"INSERT INTO bots ({', '.join(BOT_FIELDS)}, created_at, updated_at) "
                f"VALUES ({', '.join('?' * len(BOT_FIELDS))}, ?, ?)",
                (*values.values(), ts, ts),
            )
            bot_id = cur.lastrowid
        return self.get_bot(bot_id)

    def update_bot(self, bot_id: int, **fields) -> dict:
        if "params" in fields:
            fields["params"] = json.dumps(fields["params"])
        fields["updated_at"] = now()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self.conn() as c:
            c.execute(f"UPDATE bots SET {cols} WHERE id=?", (*fields.values(), bot_id))
        return self.get_bot(bot_id)

    def delete_bot(self, bot_id: int):
        with self.conn() as c:
            c.execute("DELETE FROM bots WHERE id=?", (bot_id,))
            c.execute("DELETE FROM orders WHERE bot_id=?", (bot_id,))
            c.execute("DELETE FROM logs WHERE bot_id=?", (bot_id,))

    # --- orders ---
    def add_order(self, bot_id, side, quantity, price, mode, reason="", exchange_order_id=None, raw=None):
        with self.conn() as c:
            c.execute(
                "INSERT INTO orders (bot_id, ts, side, quantity, price, mode, reason, exchange_order_id, raw) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (bot_id, now(), side, quantity, price, mode, reason, exchange_order_id,
                 json.dumps(raw) if raw is not None else None),
            )

    def list_orders(self, bot_id=None, limit=100):
        q, args = "SELECT id, bot_id, ts, side, quantity, price, mode, reason, exchange_order_id FROM orders", []
        if bot_id is not None:
            q += " WHERE bot_id=?"
            args.append(bot_id)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self.conn() as c:
            return [dict(r) for r in c.execute(q, args)]

    # --- logs ---
    def log(self, bot_id, level, message):
        with self.conn() as c:
            c.execute("INSERT INTO logs (bot_id, ts, level, message) VALUES (?, ?, ?, ?)",
                      (bot_id, now(), level, message))

    def list_logs(self, bot_id=None, limit=200):
        q, args = "SELECT * FROM logs", []
        if bot_id is not None:
            q += " WHERE bot_id=?"
            args.append(bot_id)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self.conn() as c:
            return [dict(r) for r in c.execute(q, args)]
