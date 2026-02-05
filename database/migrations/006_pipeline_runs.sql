CREATE TABLE IF NOT EXISTS pipeline_runs (
  id INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  activities_processed INTEGER,
  streams_processed INTEGER,
  weather_processed INTEGER,
  message TEXT
);
