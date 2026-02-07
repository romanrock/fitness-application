CREATE TABLE IF NOT EXISTS job_runs (
  id INTEGER PRIMARY KEY,
  job_name TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  attempts INTEGER,
  error TEXT,
  duration_sec REAL
);

CREATE INDEX IF NOT EXISTS idx_job_runs_name_started
  ON job_runs(job_name, started_at);

CREATE TABLE IF NOT EXISTS job_state (
  job_name TEXT PRIMARY KEY,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  cooldown_until TEXT,
  last_started_at TEXT,
  last_finished_at TEXT,
  last_status TEXT,
  last_error TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_dead_letters (
  id INTEGER PRIMARY KEY,
  job_name TEXT NOT NULL,
  failed_at TEXT NOT NULL,
  error TEXT,
  attempts INTEGER,
  last_status TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_dead_letters_name_time
  ON job_dead_letters(job_name, failed_at);
