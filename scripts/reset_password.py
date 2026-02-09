import argparse
import getpass
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.auth import hash_password
from packages.config import DB_PATH


def prompt_password() -> str:
    pw = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm password: ")
    if pw != confirm:
        raise SystemExit("Passwords do not match.")
    if not pw:
        raise SystemExit("Password cannot be empty.")
    return pw


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a user's password (admin/local only).")
    parser.add_argument("username")
    parser.add_argument("--password")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit("DB not initialized. Run scripts/init_db.py first.")

    password = args.password or prompt_password()
    pw_hash = hash_password(password)

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username=?", (args.username,))
        row = cur.fetchone()
        if not row:
            raise SystemExit("User not found. Use scripts/create_user.py to create the user.")
        user_id = row[0]
        cur.execute("UPDATE users SET password_hash=? WHERE id=?", (pw_hash, user_id))
        try:
            cur.execute("DELETE FROM refresh_tokens WHERE user_id=?", (user_id,))
        except sqlite3.OperationalError:
            pass
        conn.commit()
    print(f"Password reset for {args.username} (id={user_id}).")


if __name__ == "__main__":
    main()
