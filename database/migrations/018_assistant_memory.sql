ALTER TABLE insight_sessions ADD COLUMN session_id TEXT;

CREATE INDEX IF NOT EXISTS idx_insight_sessions_session ON insight_sessions(user_id, session_id, id);

CREATE TABLE IF NOT EXISTS assistant_memory (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  summary_json TEXT NOT NULL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  last_session_id INTEGER DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_assistant_memory_user ON assistant_memory(user_id);
