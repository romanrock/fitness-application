import argparse
import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SKIP_TABLES = {"schema_migrations"}


def list_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall() if r and r[0]]
    return sorted(t for t in tables if t not in SKIP_TABLES)


def export_table(conn: sqlite3.Connection, table: str, out_path: Path) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in (cur.description or [])]
    rows = cur.fetchall()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return len(rows)


def main() -> None:
    p = argparse.ArgumentParser(description="Export SQLite tables to CSV (one file per table).")
    p.add_argument("--sqlite-path", default="./data/fitness.db")
    p.add_argument("--out-dir", default=None, help="Defaults to ./data/sqlite_export_<timestamp>/")
    args = p.parse_args()

    sqlite_path = Path(args.sqlite_path).expanduser().resolve()
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite DB not found: {sqlite_path}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir) if args.out_dir else Path("./data") / f"sqlite_export_{ts}"
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(sqlite_path)) as conn:
        tables = list_tables(conn)
        if not tables:
            raise SystemExit("No tables found to export.")
        counts: dict[str, int] = {}
        for t in tables:
            n = export_table(conn, t, out_dir / f"{t}.csv")
            counts[t] = n

    manifest = out_dir / "manifest.txt"
    with manifest.open("w") as f:
        for t in tables:
            f.write(f"{t}\t{counts[t]}\n")

    print(f"Exported {len(tables)} tables to {out_dir}")
    print(f"Wrote {manifest}")


if __name__ == "__main__":
    main()

