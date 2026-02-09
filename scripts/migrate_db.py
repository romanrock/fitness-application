from pathlib import Path

from packages import db


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = db.migrations_dir()


def ensure_migrations_table(conn):
    if db.is_postgres():
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              id SERIAL PRIMARY KEY,
              filename TEXT UNIQUE NOT NULL,
              applied_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        return
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
    if db.is_postgres():
        conn.execute(
            "INSERT INTO schema_migrations(filename) VALUES(?) ON CONFLICT(filename) DO NOTHING",
            (path.name,),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(filename) VALUES(?)",
            (path.name,),
        )


def main():
    if not db.is_postgres():
        db_path = ROOT / "data" / "fitness.db"
        if not db_path.exists():
            raise SystemExit("DB not initialized. Run scripts/init_db.py")
    if not MIGRATIONS_DIR.exists():
        print("No migrations directory found.")
        return
    with db.connect() as conn:
        db.configure_connection(conn)
        already = applied_migrations(conn)
        pending = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in already)
        if not pending:
            print("No pending migrations.")
            return
        for p in pending:
            apply_migration(conn, p)
            print(f"Applied {p.name}")
        if not db.is_postgres():
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
