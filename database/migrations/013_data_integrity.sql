-- Phase 2: data integrity + idempotency

-- Deduplicate weather_raw by (user_id, activity_id), keep oldest row
DELETE FROM weather_raw
WHERE id NOT IN (
  SELECT MIN(id)
  FROM weather_raw
  GROUP BY user_id, activity_id
);

-- Enforce idempotent weather ingestion per user+activity
CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_raw_user_activity_unique
  ON weather_raw(user_id, activity_id);

-- Helpful lookup for raw activities per user
CREATE INDEX IF NOT EXISTS idx_activities_raw_user_activity
  ON activities_raw(user_id, activity_id);

-- Helpful lookup for normalized activities per user
CREATE INDEX IF NOT EXISTS idx_activities_norm_activity
  ON activities_norm(activity_id);
