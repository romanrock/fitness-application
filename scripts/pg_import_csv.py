import argparse
import csv
import os
from pathlib import Path


def _require_psycopg2():
    try:
        import psycopg2  # type: ignore
        import psycopg2.sql  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"psycopg2 is required for Postgres import: {exc}")
    return psycopg2, psycopg2.sql


# A safe order for FK dependencies (subset is OK; missing tables are skipped).
IMPORT_ORDER = [
    "sources",
    "users",
    "refresh_tokens",
    "source_sync_state",
    "activities_raw",
    "streams_raw",
    "weather_raw",
    "context_events",
    "objective_profiles",
    "insight_sessions",
    "assistant_memory",
    "pipeline_runs",
    "job_state",
    "job_runs",
    "job_dead_letters",
    # Derived tables (optional to import; can be recomputed by pipeline)
    "activities",
    "activities_calc",
    "activities_norm",
    "activity_details_run",
    "segments_best",
]


SEQ_TABLES = [
    # Tables with SERIAL/BIGSERIAL ids that we commonly import explicit IDs for.
    "sources",
    "users",
    "refresh_tokens",
    "source_sync_state",
    "activities_raw",
    "streams_raw",
    "weather_raw",
    "context_events",
    "objective_profiles",
    "insight_sessions",
    "assistant_memory",
    "pipeline_runs",
    "job_runs",
    "job_dead_letters",
    "activities",
    "activities_calc",
    "activities_norm",
    "activity_details_run",
    "segments_best",
]


def read_header(csv_path: Path) -> list[str]:
    with csv_path.open("r", newline="") as f:
        r = csv.reader(f)
        header = next(r, [])
    return [h.strip() for h in header if h and h.strip()]


def main() -> None:
    p = argparse.ArgumentParser(description="Import CSV exports into Postgres using COPY.")
    p.add_argument("--csv-dir", required=True, help="Directory containing <table>.csv files.")
    p.add_argument("--db-url", default=os.getenv("FITNESS_DB_URL", ""), help="Postgres URL; defaults to FITNESS_DB_URL.")
    p.add_argument("--truncate", action="store_true", help="TRUNCATE target tables before import (destructive).")
    p.add_argument("--no-derived", action="store_true", help="Skip importing derived tables (activities*, segments_best).")
    args = p.parse_args()

    db_url = args.db_url
    if not db_url or not db_url.startswith("postgres"):
        raise SystemExit("Set --db-url (postgresql://...) or FITNESS_DB_URL before importing.")

    csv_dir = Path(args.csv_dir).expanduser().resolve()
    if not csv_dir.exists():
        raise SystemExit(f"CSV dir not found: {csv_dir}")

    psycopg2, sql = _require_psycopg2()

    order = IMPORT_ORDER[:]
    if args.no_derived:
        order = [t for t in order if t not in {"activities", "activities_calc", "activities_norm", "activity_details_run", "segments_best"}]

    with psycopg2.connect(db_url) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            if args.truncate:
                # Reverse order and CASCADE to satisfy FKs.
                for t in reversed(order):
                    cur.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(sql.Identifier(t)))

            imported = 0
            for t in order:
                csv_path = csv_dir / f"{t}.csv"
                if not csv_path.exists():
                    continue
                cols = read_header(csv_path)
                if not cols:
                    continue
                copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)").format(
                    sql.Identifier(t),
                    sql.SQL(", ").join(sql.Identifier(c) for c in cols),
                )
                with csv_path.open("r") as f:
                    cur.copy_expert(copy_stmt.as_string(conn), f)
                imported += 1

            # If we imported explicit ids, bump sequences so future inserts don't collide.
            for t in SEQ_TABLES:
                csv_path = csv_dir / f"{t}.csv"
                if not csv_path.exists():
                    continue
                cols = read_header(csv_path)
                if "id" not in cols:
                    continue
                cur.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM {}), 1), true)"
                    ).format(sql.Identifier(t)),
                    (t,),
                )

        conn.commit()

    print(f"Imported from {csv_dir} into Postgres.")


if __name__ == "__main__":
    main()
