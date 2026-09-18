"""SQLite access helpers."""

import sqlite3

from config import DB_PATH


# One connection for the whole backend. check_same_thread is off because FastAPI
# answers requests from several threads.
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row


def query(sql, params=()):
    """Run a SELECT and return the rows as a list of dictionaries."""
    return [dict(row) for row in _conn.execute(sql, params).fetchall()]


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    _conn.execute(sql, params)
    _conn.commit()
