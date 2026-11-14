"""SQLite helpers: connection per request, query shortcuts, schema setup."""
import os
import sqlite3
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def q(sql, args=(), one=False):
    """Run a SELECT. Returns all rows, or the first row (or None) when one=True."""
    rows = get_db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows


def n(sql, args=()):
    """Return the first column of the first row (for COUNT/SUM queries)."""
    return q(sql, args, one=True)[0]


def run(sql, args=()):
    """Run an INSERT/UPDATE/DELETE, commit, and return the last row id."""
    cur = get_db().execute(sql, args)
    get_db().commit()
    return cur.lastrowid


def init_db():
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        get_db().executescript(f.read())
    if current_app.config.get("SEED_DEMO_DATA") and not q("SELECT 1 FROM users LIMIT 1"):
        from .seed import seed_demo_data
        seed_demo_data()


def init_app(app):
    app.teardown_appcontext(close_db)
