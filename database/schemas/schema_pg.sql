-- Core schema (Postgres)
-- NOTE: This is a bootstrap schema. Keep in sync with migrations_pg.

CREATE TABLE IF NOT EXISTS schema_migrations (
  id SERIAL PRIMARY KEY,
  filename TEXT UNIQUE NOT NULL,
  applied_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sources (
  id BIGSERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS activities_raw (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT NOT NULL,
  activity_id TEXT NOT NULL,
  start_time TIMESTAMPTZ,
  raw_json TEXT NOT NULL,
  user_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source_id, activity_id),
  FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS streams_raw (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT NOT NULL,
  activity_id TEXT NOT NULL,
  stream_type TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  user_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source_id, activity_id, stream_type),
  FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS weather_raw (
  id BIGSERIAL PRIMARY KEY,
  activity_id TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  user_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS activities_norm (
  id BIGSERIAL PRIMARY KEY,
  activity_id TEXT NOT NULL,
  avg_hr_norm DOUBLE PRECISION,
  flat_pace_sec DOUBLE PRECISION,
  flat_pace_weather_sec DOUBLE PRECISION,
  cadence_avg DOUBLE PRECISION,
  stride_len DOUBLE PRECISION,
  hr_drift DOUBLE PRECISION,
  decoupling DOUBLE PRECISION,
  hr_norm_json TEXT,
  pace_smooth_json TEXT,
  cadence_smooth_json TEXT,
  hr_smooth_json TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(activity_id)
);

CREATE TABLE IF NOT EXISTS activities_calc (
  id BIGSERIAL PRIMARY KEY,
  activity_id TEXT NOT NULL,
  start_time TIMESTAMPTZ,
  activity_type TEXT,
  distance_m DOUBLE PRECISION,
  moving_s DOUBLE PRECISION,
  avg_speed_mps DOUBLE PRECISION,
  avg_hr_raw DOUBLE PRECISION,
  avg_hr_norm DOUBLE PRECISION,
  flat_pace_sec DOUBLE PRECISION,
  flat_pace_weather_sec DOUBLE PRECISION,
  flat_time DOUBLE PRECISION,
  flat_dist DOUBLE PRECISION,
  cadence_avg DOUBLE PRECISION,
  stride_len DOUBLE PRECISION,
  hr_drift DOUBLE PRECISION,
  decoupling DOUBLE PRECISION,
  hr_z1_s DOUBLE PRECISION,
  hr_z2_s DOUBLE PRECISION,
  hr_z3_s DOUBLE PRECISION,
  hr_z4_s DOUBLE PRECISION,
  hr_z5_s DOUBLE PRECISION,
  hr_zone_score DOUBLE PRECISION,
  hr_zone_label TEXT,
  hr_max_used DOUBLE PRECISION,
  hr_rest_used DOUBLE PRECISION,
  hr_zone_method TEXT,
  user_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(activity_id)
);

CREATE TABLE IF NOT EXISTS activities (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT,
  activity_id TEXT NOT NULL UNIQUE,
  activity_type TEXT NOT NULL,
  start_time TIMESTAMPTZ,
  name TEXT,
  distance_m DOUBLE PRECISION,
  moving_s DOUBLE PRECISION,
  elev_gain DOUBLE PRECISION,
  user_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS activity_details_run (
  id BIGSERIAL PRIMARY KEY,
  activity_id TEXT NOT NULL UNIQUE,
  avg_hr_raw DOUBLE PRECISION,
  avg_hr_norm DOUBLE PRECISION,
  flat_pace_sec DOUBLE PRECISION,
  flat_pace_weather_sec DOUBLE PRECISION,
  cadence_avg DOUBLE PRECISION,
  stride_len DOUBLE PRECISION,
  hr_drift DOUBLE PRECISION,
  decoupling DOUBLE PRECISION,
  hr_z1_s DOUBLE PRECISION,
  hr_z2_s DOUBLE PRECISION,
  hr_z3_s DOUBLE PRECISION,
  hr_z4_s DOUBLE PRECISION,
  hr_z5_s DOUBLE PRECISION,
  hr_zone_score DOUBLE PRECISION,
  hr_zone_label TEXT,
  hr_max_used DOUBLE PRECISION,
  hr_rest_used DOUBLE PRECISION,
  hr_zone_method TEXT,
  FOREIGN KEY (activity_id) REFERENCES activities(activity_id)
);

CREATE TABLE IF NOT EXISTS segments_best (
  id BIGSERIAL PRIMARY KEY,
  distance_m INTEGER NOT NULL,
  time_s DOUBLE PRECISION,
  activity_id TEXT,
  scope TEXT NOT NULL,
  date TEXT
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL,
  token TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  revoked INTEGER DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS context_events (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  source TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS objective_profiles (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL,
  profile_json TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS insight_sessions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL,
  session_date DATE NOT NULL,
  session_id TEXT,
  prompt_json TEXT,
  response_json TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS assistant_memory (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  summary_json TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_session_id BIGINT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id BIGSERIAL PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  activities_processed INTEGER,
  streams_processed INTEGER,
  weather_processed INTEGER,
  message TEXT,
  duration_sec DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS job_runs (
  id BIGSERIAL PRIMARY KEY,
  job_name TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  attempts INTEGER,
  error TEXT,
  duration_sec DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS job_state (
  job_name TEXT PRIMARY KEY,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  cooldown_until TIMESTAMPTZ,
  last_started_at TIMESTAMPTZ,
  last_finished_at TIMESTAMPTZ,
  last_status TEXT,
  last_error TEXT,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS job_dead_letters (
  id BIGSERIAL PRIMARY KEY,
  job_name TEXT NOT NULL,
  failed_at TIMESTAMPTZ NOT NULL,
  error TEXT,
  attempts INTEGER,
  last_status TEXT
);

CREATE TABLE IF NOT EXISTS source_sync_state (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  last_activity_time BIGINT,
  access_token TEXT,
  refresh_token TEXT,
  expires_at BIGINT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source_id, user_id),
  FOREIGN KEY (source_id) REFERENCES sources(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time);
CREATE INDEX IF NOT EXISTS idx_activities_user_start_time ON activities(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_activities_activity_type ON activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_activities_user_type_time ON activities(user_id, lower(activity_type), start_time);
CREATE INDEX IF NOT EXISTS idx_activities_raw_user_activity ON activities_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_streams_raw_user_activity ON streams_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_streams_raw_user_activity_stream ON streams_raw(user_id, activity_id, stream_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_raw_user_activity_unique ON weather_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_weather_raw_user_activity ON weather_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_activities_calc_user_activity ON activities_calc(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_activities_calc_user_time ON activities_calc(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_activities_norm_activity ON activities_norm(activity_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_context_events_user_time ON context_events(user_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_objective_profiles_user ON objective_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_insight_sessions_user_date ON insight_sessions(user_id, session_date);
CREATE INDEX IF NOT EXISTS idx_insight_sessions_session ON insight_sessions(user_id, session_id, id);
CREATE INDEX IF NOT EXISTS idx_assistant_memory_user ON assistant_memory(user_id);
CREATE INDEX IF NOT EXISTS idx_segments_best_scope_distance ON segments_best(scope, distance_m);
CREATE INDEX IF NOT EXISTS idx_segments_best_scope_activity ON segments_best(scope, activity_id);
CREATE INDEX IF NOT EXISTS idx_source_sync_state_user ON source_sync_state(user_id);
CREATE INDEX IF NOT EXISTS idx_job_runs_name_started ON job_runs(job_name, started_at);
CREATE INDEX IF NOT EXISTS idx_job_dead_letters_name_time ON job_dead_letters(job_name, failed_at);

-- View: metrics_weekly (Postgres)
DROP VIEW IF EXISTS metrics_weekly;
CREATE VIEW metrics_weekly AS
WITH base AS (
  SELECT
    date_trunc('week', start_time)::date AS week,
    activity_id,
    activity_type,
    distance_m,
    moving_s,
    avg_speed_mps,
    avg_hr_norm,
    avg_hr_raw,
    flat_pace_sec,
    flat_pace_weather_sec,
    flat_time,
    flat_dist,
    cadence_avg,
    stride_len,
    start_time
  FROM activities_calc
  WHERE lower(activity_type) = 'run'
),
weekly AS (
  SELECT
    week,
    COUNT(*) AS runs,
    SUM(distance_m) AS distance_m,
    SUM(moving_s) AS moving_s,
    SUM(avg_speed_mps) AS speed_sum,
    SUM(CASE WHEN avg_speed_mps IS NOT NULL THEN 1 ELSE 0 END) AS speed_n,
    SUM(COALESCE(avg_hr_norm, avg_hr_raw)) AS hr_sum,
    SUM(CASE WHEN COALESCE(avg_hr_norm, avg_hr_raw) IS NOT NULL THEN 1 ELSE 0 END) AS hr_n,
    SUM(CASE WHEN cadence_avg IS NOT NULL THEN cadence_avg ELSE 0 END) AS cadence_sum,
    SUM(CASE WHEN cadence_avg IS NOT NULL THEN 1 ELSE 0 END) AS cadence_n,
    SUM(CASE WHEN flat_time IS NOT NULL THEN flat_time ELSE 0 END) AS flat_time_sum,
    SUM(CASE WHEN flat_dist IS NOT NULL THEN flat_dist ELSE 0 END) AS flat_dist_sum,
    AVG(flat_pace_weather_sec) AS flat_pace_weather_sec
  FROM base
  GROUP BY week
),
weekly_calc AS (
  SELECT
    week,
    runs,
    distance_m,
    moving_s,
    CASE WHEN distance_m > 0 AND moving_s > 0 THEN moving_s / (distance_m / 1000.0) END AS avg_pace_sec,
    CASE WHEN flat_dist_sum > 0 THEN (flat_time_sum / flat_dist_sum) * 1000.0 END AS flat_pace_sec,
    flat_pace_weather_sec,
    CASE WHEN hr_n > 0 THEN hr_sum / hr_n END AS avg_hr_norm,
    CASE WHEN cadence_n > 0 THEN cadence_sum / cadence_n END AS cadence_avg,
    CASE WHEN speed_n > 0 THEN speed_sum / speed_n END AS avg_speed_mps
  FROM weekly
),
weekly_more AS (
  SELECT
    week,
    runs,
    distance_m,
    moving_s,
    avg_pace_sec,
    flat_pace_sec,
    flat_pace_weather_sec,
    avg_hr_norm,
    cadence_avg,
    CASE WHEN avg_speed_mps IS NOT NULL AND cadence_avg IS NOT NULL AND cadence_avg > 0 THEN (avg_speed_mps * 60.0 / cadence_avg) END AS stride_len,
    CASE WHEN avg_speed_mps IS NOT NULL AND avg_hr_norm IS NOT NULL THEN (avg_speed_mps / avg_hr_norm) END AS eff_index
  FROM weekly_calc
),
weekly_roll AS (
  SELECT
    *,
    AVG(avg_pace_sec) OVER (ORDER BY week ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS roll_pace_sec,
    AVG(avg_hr_norm) OVER (ORDER BY week ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS roll_hr,
    AVG(distance_m / 1000.0) OVER (ORDER BY week ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS roll_dist
  FROM weekly_more
),
weeks AS (
  SELECT DISTINCT week FROM weekly_more
),
daily AS (
  SELECT
    w.week,
    gs.day::date AS day,
    COALESCE(SUM(b.distance_m), 0) AS dist_m
  FROM weeks w
  CROSS JOIN LATERAL generate_series(w.week::timestamp, w.week::timestamp + interval '6 days', interval '1 day') AS gs(day)
  LEFT JOIN base b ON date(b.start_time) = gs.day::date AND b.week = w.week
  GROUP BY w.week, gs.day
),
daily_stats AS (
  SELECT
    week,
    AVG(dist_m) AS mean_dist,
    AVG(dist_m * dist_m) AS mean_sq,
    SUM(dist_m) AS load_m
  FROM daily
  GROUP BY week
),
mono AS (
  SELECT
    week,
    CASE
      WHEN (mean_sq - mean_dist * mean_dist) > 0
      THEN mean_dist / sqrt(mean_sq - mean_dist * mean_dist)
    END AS monotony,
    load_m
  FROM daily_stats
)
SELECT
  w.week,
  w.runs,
  w.distance_m,
  w.moving_s,
  w.avg_pace_sec,
  w.flat_pace_sec,
  w.flat_pace_weather_sec,
  w.avg_hr_norm,
  w.cadence_avg,
  w.stride_len,
  w.eff_index,
  w.roll_pace_sec,
  w.roll_hr,
  w.roll_dist,
  m.monotony,
  CASE WHEN m.monotony IS NOT NULL THEN (m.monotony * (m.load_m / 1000.0)) END AS strain
FROM weekly_roll w
LEFT JOIN mono m ON m.week = w.week;
