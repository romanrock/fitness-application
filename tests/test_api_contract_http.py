import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from apps.api.schemas import ActivitiesResponse, InsightsResponse, InsightsSeriesResponse, WeeklyResponse
from tests.fixtures.build_fixture_db import build_fixture_db


@pytest.fixture()
def client():
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "fixture.db"
        build_fixture_db(db_path)

        os.environ["FITNESS_DB_PATH"] = str(db_path)
        os.environ["FITNESS_DB_URL"] = ""
        os.environ["FITNESS_AUTH_DISABLED"] = "1"

        import packages.config as config
        importlib.reload(config)
        import services.processing.pipeline as pipeline
        importlib.reload(pipeline)
        pipeline.process()

        import apps.api.main as api_main
        importlib.reload(api_main)

        with TestClient(api_main.app) as client:
            yield client


def test_weekly_contract_http(client):
    resp = client.get("/api/v1/weekly?limit=2")
    assert resp.status_code == 200
    WeeklyResponse.model_validate(resp.json())


def test_activities_contract_http(client):
    resp = client.get("/api/v1/activities?type=run&limit=5")
    assert resp.status_code == 200
    ActivitiesResponse.model_validate(resp.json())


def test_insights_contract_http(client):
    resp = client.get("/api/v1/insights")
    assert resp.status_code == 200
    InsightsResponse.model_validate(resp.json())


def test_insights_series_contract_http(client):
    resp = client.get("/api/v1/insights/series?metric=volume&weeks=12")
    assert resp.status_code == 200
    InsightsSeriesResponse.model_validate(resp.json())
