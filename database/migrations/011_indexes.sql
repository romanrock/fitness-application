-- Additional indexes for API performance
CREATE INDEX IF NOT EXISTS idx_activities_user_start_time ON activities(user_id, start_time);
CREATE INDEX IF NOT EXISTS idx_activities_activity_type ON activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_streams_raw_user_activity ON streams_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_weather_raw_user_activity ON weather_raw(user_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_activities_calc_user_activity ON activities_calc(user_id, activity_id);
