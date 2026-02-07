import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "fitness.db"
MIGRATIONS_DIR = ROOT / "database" / "migrations"


def configure_sqlite(conn):
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.OperationalError:
        return


def ensure_migrations_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          id INTEGER PRIMARY KEY,
          filename TEXT UNIQUE NOT NULL,
          applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def applied_migrations(conn):
    ensure_migrations_table(conn)
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def apply_migration(conn, path):
    sql = path.read_text()
    conn.executescript(sql)
    conn.execute(
        "INSERT INTO schema_migrations(filename) VALUES(?)",
        (path.name,),
    )


def main():
    if not DB_PATH.exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py")
    if not MIGRATIONS_DIR.exists():
        print("No migrations directory found.")
        return
    with sqlite3.connect(DB_PATH) as conn:
        configure_sqlite(conn)
        already = applied_migrations(conn)
        pending = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in already)
        if not pending:
            print("No pending migrations.")
            return
        for p in pending:
            apply_migration(conn, p)
            print(f"Applied {p.name}")
        fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_issues:
            print("Foreign key violations detected:")
            for row in fk_issues[:10]:
                print(row)
            raise SystemExit("Foreign key check failed.")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if integrity and integrity[0] != "ok":
            raise SystemExit(f"Integrity check failed: {integrity[0]}")


if __name__ == "__main__":
    main()
