import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.auth import hash_password, validate_password
from packages import db


def main():
    parser = argparse.ArgumentParser(description="Create or update a user.")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--assign-existing", action="store_true", default=False)
    args = parser.parse_args()

    if not db.db_exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py first.")

    with db.connect() as conn:
        db.configure_connection(conn)
        if not db.is_postgres():
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
        try:
            validate_password(args.password, args.username)
        except ValueError as exc:
            raise SystemExit(str(exc))
        pw_hash = hash_password(args.password)
        cur.execute("SELECT id FROM users WHERE username=?", (args.username,))
        row = cur.fetchone()
        if row:
            user_id = row[0]
            cur.execute("UPDATE users SET password_hash=? WHERE id=?", (pw_hash, user_id))
        else:
            cur.execute(
                "INSERT INTO users(username, password_hash) VALUES(?,?)",
                (args.username, pw_hash),
            )
            user_id = cur.lastrowid
        if args.assign_existing:
            conn.execute("UPDATE activities_raw SET user_id=? WHERE user_id IS NULL", (user_id,))
            conn.execute("UPDATE streams_raw SET user_id=? WHERE user_id IS NULL", (user_id,))
            conn.execute("UPDATE weather_raw SET user_id=? WHERE user_id IS NULL", (user_id,))
            conn.execute("UPDATE activities SET user_id=? WHERE user_id IS NULL", (user_id,))
            conn.execute("UPDATE activities_calc SET user_id=? WHERE user_id IS NULL", (user_id,))
        conn.commit()
    print(f"User ready: {args.username} (id={user_id})")


if __name__ == "__main__":
    main()
