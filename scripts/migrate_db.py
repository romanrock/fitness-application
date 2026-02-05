import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "fitness.db"
MIGRATIONS_DIR = ROOT / "database" / "migrations"


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
        already = applied_migrations(conn)
        pending = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in already)
        if not pending:
            print("No pending migrations.")
            return
        for p in pending:
            apply_migration(conn, p)
            print(f"Applied {p.name}")


if __name__ == "__main__":
    main()
