CREATE TABLE IF NOT EXISTS context_events (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  source TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS objective_profiles (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  profile_json TEXT NOT NULL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS insight_sessions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  session_date TEXT NOT NULL,
  prompt_json TEXT,
  response_json TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_context_events_user_time ON context_events(user_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_objective_profiles_user ON objective_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_insight_sessions_user_date ON insight_sessions(user_id, session_date);
