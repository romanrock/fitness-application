from apps.api.main import app


def test_versioned_health_routes_exist():
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/health" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/activities" in paths
