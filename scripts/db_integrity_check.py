from packages import db


def main():
    if not db.db_exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py")
    with db.connect() as conn:
        db.configure_connection(conn)
        if db.is_postgres():
            conn.execute("SELECT 1")
            print("DB integrity OK (Postgres checks skipped).")
            return
        fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_issues:
            print("Foreign key violations detected:")
            for row in fk_issues[:10]:
                print(row)
            raise SystemExit("Foreign key check failed.")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if integrity and integrity[0] != "ok":
            raise SystemExit(f"Integrity check failed: {integrity[0]}")
    print("DB integrity OK.")


if __name__ == "__main__":
    main()
