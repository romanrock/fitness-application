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
  prompt_json TEXT,
  response_json TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_context_events_user_time ON context_events(user_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_objective_profiles_user ON objective_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_insight_sessions_user_date ON insight_sessions(user_id, session_date);
