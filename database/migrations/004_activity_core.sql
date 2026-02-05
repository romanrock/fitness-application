-- Canonical activity tables for app navigation.

CREATE TABLE IF NOT EXISTS activities (
  id INTEGER PRIMARY KEY,
  source_id INTEGER,
  activity_id TEXT NOT NULL UNIQUE,
  activity_type TEXT NOT NULL,
  start_time TEXT,
  name TEXT,
  distance_m REAL,
  moving_s REAL,
  elev_gain REAL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS activity_details_run (
  id INTEGER PRIMARY KEY,
  activity_id TEXT NOT NULL UNIQUE,
  avg_hr_raw REAL,
  avg_hr_norm REAL,
  flat_pace_sec REAL,
  flat_pace_weather_sec REAL,
  cadence_avg REAL,
  stride_len REAL,
  hr_drift REAL,
  decoupling REAL,
  FOREIGN KEY (activity_id) REFERENCES activities(activity_id)
);

CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time);
