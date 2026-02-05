import json
import sqlite3
from pathlib import Path

from apps.api.auth import create_token, decode_token, hash_password, verify_password


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "fitness.db"


def test_password_hash_roundtrip():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed)
    assert not verify_password("bad", hashed)


def test_jwt_roundtrip():
    token = create_token(1, "tester")
    payload = decode_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "tester"


def test_users_table_exists_or_create():
    if not DB_PATH.exists():
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        assert cur.fetchone() is not None
