import json
import sqlite3
from pathlib import Path


def apply_schema_and_migrations(conn: sqlite3.Connection, root: Path) -> None:
    schema_path = root / "database" / "schemas" / "schema.sql"
    conn.executescript(schema_path.read_text())

    migrations_dir = root / "database" / "migrations"
    if migrations_dir.exists():
        for path in sorted(migrations_dir.glob("*.sql")):
            sql = path.read_text()
            for statement in sql.split(";"):
                stmt = statement.strip()
                if not stmt:
                    continue
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    msg = str(exc)
                    if "duplicate column name" in msg or "already exists" in msg:
                        continue
                    raise


def insert_stream(conn: sqlite3.Connection, source_id: int, activity_id: str, stream_type: str, data, user_id: int) -> None:
    payload = json.dumps({"data": data})
    conn.execute(
        "INSERT INTO streams_raw(source_id, activity_id, stream_type, raw_json, user_id) VALUES(?,?,?,?,?)",
        (source_id, activity_id, stream_type, payload, user_id),
    )


def build_fixture_db(db_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        apply_schema_and_migrations(conn, root)
        conn.execute("INSERT INTO sources(id, name) VALUES(1, 'strava')")
        conn.execute("INSERT INTO users(id, username, password_hash) VALUES(1, 'u1', 'x')")
        conn.execute("INSERT INTO users(id, username, password_hash) VALUES(2, 'u2', 'x')")

        # Activity A: full streams
        activity_a = {
            "id": "A1",
            "name": "Run A",
            "type": "Run",
            "start_date": "2026-02-01T12:00:00Z",
            "distance": 1000.0,
            "moving_time": 300,
            "average_speed": 3.33,
            "total_elevation_gain": 5,
            "average_heartrate": 150,
        }
        conn.execute(
            "INSERT INTO activities_raw(source_id, activity_id, start_time, raw_json, user_id) VALUES(?,?,?,?,?)",
            (1, "A1", activity_a["start_date"], json.dumps(activity_a), 1),
        )

        time = [0, 60, 120, 180, 240, 300]
        dist = [0, 200, 400, 600, 800, 1000]
        alt = [0, 1, 2, 3, 4, 5]
        hr = [140, 145, 150, 155, 160, 165]
        cad = [80, 82, 84, 86, 88, 90]
        insert_stream(conn, 1, "A1", "time", time, 1)
        insert_stream(conn, 1, "A1", "distance", dist, 1)
        insert_stream(conn, 1, "A1", "altitude", alt, 1)
        insert_stream(conn, 1, "A1", "heartrate", hr, 1)
        insert_stream(conn, 1, "A1", "cadence", cad, 1)

        # Activity B: missing HR stream
        activity_b = {
            "id": "B1",
            "name": "Run B",
            "type": "Run",
            "start_date": "2026-02-02T12:00:00Z",
            "distance": 1000.0,
            "moving_time": 320,
            "average_speed": 3.12,
            "total_elevation_gain": 4,
            "average_heartrate": 155,
        }
        conn.execute(
            "INSERT INTO activities_raw(source_id, activity_id, start_time, raw_json, user_id) VALUES(?,?,?,?,?)",
            (1, "B1", activity_b["start_date"], json.dumps(activity_b), 1),
        )
        insert_stream(conn, 1, "B1", "time", time, 1)
        insert_stream(conn, 1, "B1", "distance", dist, 1)
        insert_stream(conn, 1, "B1", "altitude", alt, 1)

        # Activity C: user 2, missing HR (for decoupling meta)
        activity_c = {
            "id": "C1",
            "name": "Run C",
            "type": "Run",
            "start_date": "2026-02-02T13:00:00Z",
            "distance": 1000.0,
            "moving_time": 340,
            "average_speed": 2.94,
            "total_elevation_gain": 3,
            "average_heartrate": 140,
        }
        conn.execute(
            "INSERT INTO activities_raw(source_id, activity_id, start_time, raw_json, user_id) VALUES(?,?,?,?,?)",
            (1, "C1", activity_c["start_date"], json.dumps(activity_c), 2),
        )
        insert_stream(conn, 1, "C1", "time", time, 2)
        insert_stream(conn, 1, "C1", "distance", dist, 2)
        insert_stream(conn, 1, "C1", "altitude", alt, 2)
        conn.commit()


if __name__ == "__main__":
    build_fixture_db(Path("/tmp/fitness_fixture.db"))
