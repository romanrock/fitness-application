from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DBMissingResponse(BaseModel):
    db: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PipelineRun(BaseModel):
    id: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: Optional[str] = None
    activities_processed: Optional[int] = None
    streams_processed: Optional[int] = None
    weather_processed: Optional[int] = None
    message: Optional[str] = None
    duration_sec: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    last_update: Optional[str] = None
    pipeline: Optional[PipelineRun] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class LogoutResponse(BaseModel):
    status: str


class JobStateEntry(BaseModel):
    job_name: str
    consecutive_failures: int
    cooldown_until: Optional[str] = None
    last_started_at: Optional[str] = None
    last_finished_at: Optional[str] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    updated_at: Optional[str] = None


class JobRunEntry(BaseModel):
    id: Optional[int] = None
    job_name: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: Optional[str] = None
    attempts: Optional[int] = None
    error: Optional[str] = None
    duration_sec: Optional[float] = None


class JobsResponse(DBMissingResponse):
    jobs: List[JobStateEntry] = Field(default_factory=list)


class JobRunsResponse(DBMissingResponse):
    runs: List[JobRunEntry] = Field(default_factory=list)


class JobDeadLetterEntry(BaseModel):
    id: Optional[int] = None
    job_name: Optional[str] = None
    failed_at: Optional[str] = None
    error: Optional[str] = None
    attempts: Optional[int] = None
    last_status: Optional[str] = None


class JobDeadLettersResponse(DBMissingResponse):
    dead_letters: List[JobDeadLetterEntry] = Field(default_factory=list)


class StatsResponse(DBMissingResponse):
    activities_raw: Optional[int] = None
    streams_raw: Optional[int] = None
    weather_raw: Optional[int] = None


class WeeklyRow(BaseModel):
    week: str
    runs: Optional[int] = None
    distance_m: Optional[float] = None
    moving_s: Optional[float] = None
    avg_pace_sec: Optional[float] = None
    flat_pace_sec: Optional[float] = None
    flat_pace_weather_sec: Optional[float] = None
    avg_hr_norm: Optional[float] = None
    cadence_avg: Optional[float] = None
    stride_len: Optional[float] = None
    eff_index: Optional[float] = None
    roll_pace_sec: Optional[float] = None
    roll_hr: Optional[float] = None
    roll_dist: Optional[float] = None
    monotony: Optional[float] = None
    strain: Optional[float] = None


class WeeklyResponse(DBMissingResponse):
    weekly: List[WeeklyRow] = Field(default_factory=list)


class ActivityTotalRow(BaseModel):
    activity_type: str
    count: int
    distance_m: float


class ActivityTotalsResponse(DBMissingResponse):
    totals: List[ActivityTotalRow] = Field(default_factory=list)


class ActivitySummary(BaseModel):
    activity_id: str
    start_time: Optional[str] = None
    activity_type: Optional[str] = None
    name: Optional[str] = None
    distance_m: Optional[float] = None
    moving_s: Optional[float] = None
    elev_gain: Optional[float] = None
    avg_hr_norm: Optional[float] = None
    flat_pace_sec: Optional[float] = None
    flat_pace_weather_sec: Optional[float] = None
    cadence_avg: Optional[float] = None
    stride_len: Optional[float] = None
    hr_drift: Optional[float] = None
    decoupling: Optional[float] = None
    hr_zone_score: Optional[float] = None
    hr_zone_label: Optional[str] = None


class ActivitiesResponse(DBMissingResponse):
    activities: List[ActivitySummary] = Field(default_factory=list)


class ActivityDetailResponse(DBMissingResponse):
    activity_id: Optional[str] = None
    start_time: Optional[str] = None
    activity_type: Optional[str] = None
    name: Optional[str] = None
    distance_m: Optional[float] = None
    moving_s: Optional[float] = None
    elev_gain: Optional[float] = None
    avg_hr_raw: Optional[float] = None
    avg_hr_norm: Optional[float] = None
    flat_pace_sec: Optional[float] = None
    flat_pace_weather_sec: Optional[float] = None
    cadence_avg: Optional[float] = None
    stride_len: Optional[float] = None
    hr_drift: Optional[float] = None
    decoupling: Optional[float] = None
    hr_norm_json: Optional[str] = None
    weather: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class StreamsResponse(DBMissingResponse):
    streams: Dict[str, Any] = Field(default_factory=dict)


class LapsResponse(DBMissingResponse):
    laps: List[Dict[str, Any]] = Field(default_factory=list)
    lap_totals: Optional[Dict[str, Any]] = None


class SummaryResponse(DBMissingResponse):
    distance_m: Optional[float] = None
    moving_s: Optional[float] = None
    elev_gain: Optional[float] = None
    avg_pace_sec: Optional[float] = None
    best_pace_sec: Optional[float] = None
    avg_hr_norm: Optional[float] = None
    avg_hr_raw: Optional[float] = None
    max_hr: Optional[float] = None
    calories: Optional[float] = None
    cadence_avg: Optional[float] = None
    stride_len: Optional[float] = None
    flat_pace_sec: Optional[float] = None
    hr_zones: Optional[List[Dict[str, Any]]] = None
    hr_zone_score: Optional[float] = None
    hr_zone_label: Optional[str] = None
    hr_max_used: Optional[float] = None
    hr_rest_used: Optional[float] = None
    hr_zone_method: Optional[str] = None
    stream_status: Optional[Dict[str, bool]] = None
    summary_notes: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class InsightSeriesPoint(BaseModel):
    week: str
    value: Optional[float] = None


class InsightsSeriesMeta(BaseModel):
    reason: Optional[str] = None


class InsightsSeriesResponse(DBMissingResponse):
    metric: str
    series: List[InsightSeriesPoint] = Field(default_factory=list)
    series_meta: Optional[InsightsSeriesMeta] = None


class InsightsResponse(DBMissingResponse):
    vdot_best: Optional[float] = None
    vdot_source: Optional[Dict[str, Any]] = None
    pb_all: Dict[int, Dict[str, Any]] = Field(default_factory=dict)
    pb_12m: Dict[int, Dict[str, Any]] = Field(default_factory=dict)
    est_5k_s: Optional[float] = None
    est_10k_s: Optional[float] = None
    pace_trend_sec_per_week: Optional[float] = None
    hr_trend_bpm_per_week: Optional[float] = None
    eff_trend_per_week: Optional[float] = None
    monotony: Optional[float] = None
    strain: Optional[float] = None
    decoupling_28d: Optional[float] = None
    hr_drift_28d: Optional[float] = None
    weekly_fatigue: List[Dict[str, Any]] = Field(default_factory=list)
    fatigue_last_week: Optional[float] = None
    fatigue_4w_avg: Optional[float] = None
    recovery_index_28d: Optional[float] = None
    efficiency_trend_12w: Optional[float] = None
    dist_7d_km: Optional[float] = None
    dist_28d_km: Optional[float] = None


class SegmentBestEntry(BaseModel):
    time_s: Optional[float] = None
    activity_id: Optional[str] = None
    date: Optional[str] = None


class SegmentsBestResponse(DBMissingResponse):
    best_all: Dict[int, SegmentBestEntry] = Field(default_factory=dict)
    best_12w: Dict[int, SegmentBestEntry] = Field(default_factory=dict)


class ActivitySegmentsResponse(DBMissingResponse):
    segments: Dict[int, float] = Field(default_factory=dict)


class ActivitySeriesData(BaseModel):
    time: List[float] = Field(default_factory=list)
    pace: List[Optional[float]] = Field(default_factory=list)
    hr: List[Optional[float]] = Field(default_factory=list)
    cadence: List[Optional[float]] = Field(default_factory=list)
    elevation: List[Optional[float]] = Field(default_factory=list)


class ActivitySeriesResponse(DBMissingResponse):
    series: ActivitySeriesData = Field(default_factory=ActivitySeriesData)


class ActivityRouteResponse(DBMissingResponse):
    route: List[List[float]] = Field(default_factory=list)
