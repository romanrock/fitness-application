CREATE TABLE IF NOT EXISTS source_sync_state (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  last_activity_time INTEGER,
  access_token TEXT,
  refresh_token TEXT,
  expires_at INTEGER,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_id, user_id),
  FOREIGN KEY (source_id) REFERENCES sources(id),
  FOREIGN KEY (user_id) REFERENCES users(id)
);
