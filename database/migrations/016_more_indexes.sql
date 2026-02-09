-- Additional indexes for Phase 2 (performance + consistency)

-- Activity lists filtered by user, type, date
CREATE INDEX IF NOT EXISTS idx_activities_user_type_time
  ON activities(user_id, lower(activity_type), start_time);

-- Insights queries on recent windows
CREATE INDEX IF NOT EXISTS idx_activities_calc_user_time
  ON activities_calc(user_id, start_time);

-- Streams lookups by activity
CREATE INDEX IF NOT EXISTS idx_streams_raw_user_activity_stream
  ON streams_raw(user_id, activity_id, stream_type);

-- Segment lookups by scope
CREATE INDEX IF NOT EXISTS idx_segments_best_scope_distance
  ON segments_best(scope, distance_m);
CREATE INDEX IF NOT EXISTS idx_segments_best_scope_activity
  ON segments_best(scope, activity_id);

-- Sync state lookup by user
CREATE INDEX IF NOT EXISTS idx_source_sync_state_user
  ON source_sync_state(user_id);
