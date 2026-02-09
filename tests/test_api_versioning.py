from apps.api.main import app


def test_versioned_health_routes_exist():
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/api/health" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/activities" in paths


def test_openapi_includes_versioned_paths():
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/api/v1/health" in paths
    assert "/api/v1/activities" in paths


def test_openapi_schema_has_core_components():
    schema = app.openapi()
    assert schema.get("openapi", "").startswith("3.")
    assert schema.get("info", {}).get("title")
    paths = schema.get("paths", {})
    assert paths
    for path, ops in paths.items():
        assert isinstance(ops, dict)
        assert any(method in ops for method in ("get", "post", "put", "delete", "patch")), path
    components = schema.get("components", {}).get("schemas", {})
    for name in ("ActivitiesResponse", "WeeklyResponse", "InsightsResponse", "InsightsSeriesResponse"):
        assert name in components
