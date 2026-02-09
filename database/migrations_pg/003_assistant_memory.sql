ALTER TABLE insight_sessions ADD COLUMN IF NOT EXISTS session_id TEXT;

CREATE INDEX IF NOT EXISTS idx_insight_sessions_session ON insight_sessions(user_id, session_id, id);

CREATE TABLE IF NOT EXISTS assistant_memory (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  summary_json TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_session_id INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_assistant_memory_user ON assistant_memory(user_id);
