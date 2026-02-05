import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.fixtures.build_fixture_db import build_fixture_db


def _setup_db():
    tmp = TemporaryDirectory()
    db_path = Path(tmp.name) / "fixture.db"
    build_fixture_db(db_path)
    os.environ["FITNESS_DB_PATH"] = str(db_path)

    import packages.config as config
    importlib.reload(config)

    import services.processing.pipeline as pipeline
    importlib.reload(pipeline)
    pipeline.process()

    import apps.api.routes.activities as activities
    import apps.api.routes.insights as insights
    importlib.reload(activities)
    importlib.reload(insights)

    return tmp, activities, insights


def test_activity_summary_has_pace_and_notes():
    tmp, activities, _ = _setup_db()
    user = {"id": 1, "username": "u1"}

    summary_a = activities.activity_summary("A1", user=user)
    assert summary_a.get("flat_pace_sec") is not None
    assert summary_a.get("best_pace_sec") is not None

    summary_b = activities.activity_summary("B1", user=user)
    notes = summary_b.get("summary_notes", [])
    assert "missing_hr_streams" in notes

    tmp.cleanup()


def test_insights_recovery_index_fallback():
    tmp, _, insights = _setup_db()
    user = {"id": 1, "username": "u1"}

    payload = insights.insights(user=user)
    assert payload.get("recovery_index_28d") is not None

    tmp.cleanup()


def test_decoupling_series_meta_when_hr_missing():
    tmp, _, insights = _setup_db()
    user = {"id": 2, "username": "u2"}

    payload = insights.insights_series(metric="decoupling", weeks=52, user=user)
    meta = payload.get("series_meta") or {}
    assert meta.get("reason") == "missing_hr_streams"

    tmp.cleanup()


def test_weekly_and_volume_series_present():
    tmp, activities, insights = _setup_db()
    user = {"id": 1, "username": "u1"}

    weekly = activities.weekly(limit=10, user=user)
    assert weekly.get("weekly")

    volume_series = insights.insights_series(metric="volume", weeks=52, user=user)
    assert volume_series.get("series")

    tmp.cleanup()
