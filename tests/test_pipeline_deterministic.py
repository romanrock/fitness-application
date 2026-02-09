import importlib
import os
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tests.fixtures.build_fixture_db import build_fixture_db


def _run_pipeline(db_path: Path) -> None:
    os.environ["FITNESS_DB_PATH"] = str(db_path)
    os.environ["FITNESS_DB_URL"] = ""

    import packages.config as config
    importlib.reload(config)

    import services.processing.pipeline as pipeline
    importlib.reload(pipeline)
    pipeline.process()


def _expected_flat_pace_sec() -> float:
    time = [0, 60, 120, 180, 240, 300]
    dist = [0, 200, 400, 600, 800, 1000]
    alt = [0, 1, 2, 3, 4, 5]
    flat_time = 0.0
    total_dist = 0.0
    for i in range(1, len(time)):
        dt = time[i] - time[i - 1]
        dd = dist[i] - dist[i - 1]
        grade = (alt[i] - alt[i - 1]) / dd
        grade = max(min(grade, 0.1), -0.1)
        cost = 1 + 0.045 * grade + 0.35 * grade * grade
        flat_time += (dt / dd) * cost * dd
        total_dist += dd
    return (flat_time / total_dist) * 1000


def test_pipeline_outputs_are_deterministic():
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "fixture.db"
        build_fixture_db(db_path)
        _run_pipeline(db_path)

        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT distance_m, moving_s FROM activities_calc WHERE activity_id='A1'"
            )
            distance_m, moving_s = cur.fetchone()
            assert distance_m == pytest.approx(1000.0, rel=1e-4)
            assert moving_s == pytest.approx(300.0, rel=1e-4)

            cur.execute(
                """
                SELECT flat_pace_sec, cadence_avg, hr_drift, decoupling
                FROM activity_details_run
                WHERE activity_id='A1'
                """
            )
            flat_pace_sec, cadence_avg, hr_drift, decoupling = cur.fetchone()
            assert flat_pace_sec == pytest.approx(_expected_flat_pace_sec(), rel=1e-4)
            assert cadence_avg == pytest.approx(170.0, rel=1e-3)
            assert hr_drift is not None
            assert decoupling is not None

            cur.execute(
                """
                SELECT hr_drift, decoupling
                FROM activity_details_run
                WHERE activity_id='B1'
                """
            )
            hr_drift_b, decoupling_b = cur.fetchone()
            assert hr_drift_b is None
            assert decoupling_b is None
