import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
import urllib.request

from tests.fixtures.build_fixture_db import build_fixture_db


def wait_for(url, timeout=10):
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception as exc:
            last_err = exc
            time.sleep(0.3)
    raise RuntimeError(f"Server not ready: {last_err}")


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_http_endpoints_live():
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "fixture.db"
        build_fixture_db(db_path)

        os.environ["FITNESS_DB_PATH"] = str(db_path)
        os.environ["FITNESS_AUTH_DISABLED"] = "1"
        os.environ["FITNESS_API_PORT"] = "8002"

        import packages.config as config
        importlib.reload(config)
        import services.processing.pipeline as pipeline
        importlib.reload(pipeline)
        pipeline.process()

        env = os.environ.copy()
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--port", "8002"],
            cwd=str(root),
            env=env,
        )
        try:
            wait_for("http://127.0.0.1:8002/api/v1/health")

            health = fetch_json("http://127.0.0.1:8002/api/v1/health")
            assert health.get("status") == "ok"

            weekly = fetch_json("http://127.0.0.1:8002/api/v1/weekly?limit=1")
            assert weekly.get("weekly")

            activities = fetch_json("http://127.0.0.1:8002/api/v1/activities?type=run&limit=5")
            assert activities.get("activities")

            summary = fetch_json("http://127.0.0.1:8002/api/v1/activity/A1/summary")
            assert summary.get("flat_pace_sec") is not None

            insights = fetch_json("http://127.0.0.1:8002/api/v1/insights")
            assert insights.get("recovery_index_28d") is not None

            series = fetch_json("http://127.0.0.1:8002/api/v1/insights/series?metric=volume&weeks=12")
            assert series.get("series")

            # Error model should be consistent
            try:
                fetch_json("http://127.0.0.1:8002/api/v1/activity/NOPE/summary")
                assert False, "Expected 404"
            except urllib.error.HTTPError as err:
                body = json.loads(err.read().decode("utf-8"))
                assert err.code == 404
                assert "error" in body
                assert body["error"]["code"] == "http_404"
                assert isinstance(body["error"]["message"], str)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
