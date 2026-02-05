CREATE TABLE IF NOT EXISTS schema_migrations (
  id INTEGER PRIMARY KEY,
  filename TEXT UNIQUE NOT NULL,
  applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activities_calc (
  id INTEGER PRIMARY KEY,
  activity_id TEXT NOT NULL,
  start_time TEXT,
  distance_m REAL,
  moving_s REAL,
  avg_speed_mps REAL,
  avg_hr_raw REAL,
  avg_hr_norm REAL,
  flat_pace_sec REAL,
  flat_pace_weather_sec REAL,
  cadence_avg REAL,
  stride_len REAL,
  hr_drift REAL,
  decoupling REAL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(activity_id)
);

ALTER TABLE activities_norm ADD COLUMN hr_norm_json TEXT;
