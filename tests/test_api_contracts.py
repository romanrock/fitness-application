from apps.api.schemas import ActivitiesResponse, ActivitySeriesResponse, InsightsResponse, WeeklyResponse


def test_weekly_contract_accepts_empty():
    payload = WeeklyResponse(weekly=[])
    assert payload.weekly == []


def test_activities_contract_accepts_empty():
    payload = ActivitiesResponse(activities=[])
    assert payload.activities == []


def test_series_contract_defaults():
    payload = ActivitySeriesResponse()
    assert payload.series.time == []
    assert payload.series.pace == []


def test_insights_contract_defaults():
    payload = InsightsResponse()
    assert payload.pb_all == {}
    assert payload.pb_12m == {}
