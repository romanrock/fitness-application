import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages import db

def main() -> None:
    schema = db.schema_path()
    if not schema.exists():
        raise SystemExit(f"Schema not found: {schema}")

    if not db.is_postgres():
        db_path = ROOT / "data" / "fitness.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

    with db.connect() as conn:
        db.configure_connection(conn)
        conn.executescript(schema.read_text())
    print(f"Initialized {schema}")


if __name__ == "__main__":
    main()
