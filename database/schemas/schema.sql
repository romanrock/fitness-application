-- Core schema (SQLite)
-- NOTE: This is a bootstrap schema. Always run migrations after init.

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS activities_raw (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL,
  activity_id TEXT NOT NULL,
  start_time TEXT,
  raw_json TEXT NOT NULL,
  user_id INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_id, activity_id),
  FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS streams_raw (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL,
  activity_id TEXT NOT NULL,
  stream_type TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  user_id INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_id, activity_id, stream_type),
  FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS weather_raw (
  id INTEGER PRIMARY KEY,
  activity_id TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  user_id INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activities_norm (
  id INTEGER PRIMARY KEY,
  activity_id TEXT NOT NULL,
  avg_hr_norm REAL,
  flat_pace_sec REAL,
  flat_pace_weather_sec REAL,
  cadence_avg REAL,
  stride_len REAL,
  hr_drift REAL,
  decoupling REAL,
  hr_norm_json TEXT,
  pace_smooth_json TEXT,
  cadence_smooth_json TEXT,
  hr_smooth_json TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(activity_id)
);

CREATE TABLE IF NOT EXISTS activities_calc (
  id INTEGER PRIMARY KEY,
  activity_id TEXT NOT NULL,
  start_time TEXT,
  activity_type TEXT,
  distance_m REAL,
  moving_s REAL,
  avg_speed_mps REAL,
  avg_hr_raw REAL,
  avg_hr_norm REAL,
  flat_pace_sec REAL,
  flat_pace_weather_sec REAL,
  flat_time REAL,
  flat_dist REAL,
  cadence_avg REAL,
  stride_len REAL,
  hr_drift REAL,
  decoupling REAL,
  user_id INTEGER,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(activity_id)
);

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
  user_id INTEGER,
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

CREATE TABLE IF NOT EXISTS segments_best (
  id INTEGER PRIMARY KEY,
  distance_m INTEGER NOT NULL,
  time_s REAL,
  activity_id TEXT,
  scope TEXT NOT NULL,
  date TEXT
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  token TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  revoked INTEGER DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_activities_user_start_time ON activities(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_activities_activity_type ON activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_activities_raw_user_activity ON activities_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_streams_raw_user_activity ON streams_raw(user_id, activity_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_raw_user_activity_unique ON weather_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_weather_raw_user_activity ON weather_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_activities_calc_user_activity ON activities_calc(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_activities_norm_activity ON activities_norm(activity_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);

-- metrics_weekly is now a VIEW created by migrations.
