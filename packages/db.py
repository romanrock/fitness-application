import sqlite3
from pathlib import Path
from typing import Iterable, Optional

import packages.config as config

try:  # Optional dependency for Postgres
    import psycopg2
except ImportError:  # pragma: no cover - optional in SQLite-only envs
    psycopg2 = None


def is_postgres() -> bool:
    return bool(config.DB_URL) and config.DB_URL.startswith("postgres")


def db_exists() -> bool:
    if is_postgres():
        return True
    return config.DB_PATH.exists()


def _adapt_sql(sql: str) -> str:
    if not is_postgres():
        return sql
    return sql.replace("?", "%s")


class DBCursor:
    def __init__(self, cursor, postgres: bool):
        self._cursor = cursor
        self._postgres = postgres

    @property
    def description(self):
        return self._cursor.description

    def execute(self, sql: str, params: Optional[Iterable] = None):
        sql = _adapt_sql(sql) if self._postgres else sql
        if params is None:
            self._cursor.execute(sql)
        else:
            self._cursor.execute(sql, list(params))
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class DBConnection:
    def __init__(self, conn, postgres: bool):
        self._conn = conn
        self._postgres = postgres

    def cursor(self):
        return DBCursor(self._conn.cursor(), self._postgres)

    def execute(self, sql: str, params: Optional[Iterable] = None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def executescript(self, sql: str) -> None:
        if not self._postgres:
            self._conn.executescript(sql)
            return
        for stmt in _split_sql(sql):
            if stmt:
                self._conn.cursor().execute(stmt)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            try:
                self.rollback()
            finally:
                self.close()
        else:
            try:
                self.commit()
            finally:
                self.close()


def connect() -> DBConnection:
    if is_postgres():
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for Postgres. Add psycopg2-binary.")
        return DBConnection(psycopg2.connect(config.DB_URL), postgres=True)
    return DBConnection(sqlite3.connect(config.DB_PATH), postgres=False)


def configure_connection(conn: DBConnection) -> None:
    if is_postgres():
        return
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
    except sqlite3.OperationalError:
        return


def migrations_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    if is_postgres():
        return root / "database" / "migrations_pg"
    return root / "database" / "migrations"


def schema_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    if is_postgres():
        return root / "database" / "schemas" / "schema_pg.sql"
    return root / "database" / "schemas" / "schema.sql"


def _split_sql(sql: str) -> list[str]:
    parts = []
    buf = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            parts.append("\n".join(buf).strip().rstrip(";"))
            buf = []
    if buf:
        parts.append("\n".join(buf).strip().rstrip(";"))
    return parts
