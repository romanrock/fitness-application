from apps.api.schemas import LoginResponse, WeeklyRow, WeeklyResponse


def test_login_response_defaults():
    resp = LoginResponse(access_token="token")
    assert resp.token_type == "bearer"


def test_weekly_response_serializes():
    row = WeeklyRow(week="2026-01-01", runs=2)
    payload = WeeklyResponse(weekly=[row])
    assert payload.weekly[0].runs == 2
