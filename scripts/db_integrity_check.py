import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "fitness.db"


def main():
    if not DB_PATH.exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py")
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.OperationalError:
            pass
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
