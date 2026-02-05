ALTER TABLE activities_calc ADD COLUMN user_id INTEGER;

UPDATE activities_calc
SET user_id = (
  SELECT user_id FROM activities a WHERE a.activity_id = activities_calc.activity_id
)
WHERE user_id IS NULL;

DROP VIEW IF EXISTS metrics_weekly;

CREATE VIEW IF NOT EXISTS metrics_weekly AS
WITH RECURSIVE
base AS (
  SELECT
    date(start_time, 'weekday 1', '-7 days') AS week,
    user_id,
    activity_id,
    activity_type,
    distance_m,
    moving_s,
    avg_speed_mps,
    avg_hr_norm,
    avg_hr_raw,
    flat_pace_sec,
    flat_pace_weather_sec,
    flat_time,
    flat_dist,
    cadence_avg,
    stride_len,
    start_time
  FROM activities_calc
  WHERE lower(activity_type) = 'run'
),
weekly AS (
  SELECT
    week,
    user_id,
    COUNT(*) AS runs,
    SUM(distance_m) AS distance_m,
    SUM(moving_s) AS moving_s,
    SUM(avg_speed_mps) AS speed_sum,
    SUM(CASE WHEN avg_speed_mps IS NOT NULL THEN 1 ELSE 0 END) AS speed_n,
    SUM(COALESCE(avg_hr_norm, avg_hr_raw)) AS hr_sum,
    SUM(CASE WHEN COALESCE(avg_hr_norm, avg_hr_raw) IS NOT NULL THEN 1 ELSE 0 END) AS hr_n,
    SUM(CASE WHEN cadence_avg IS NOT NULL THEN cadence_avg ELSE 0 END) AS cadence_sum,
    SUM(CASE WHEN cadence_avg IS NOT NULL THEN 1 ELSE 0 END) AS cadence_n,
    SUM(CASE WHEN flat_time IS NOT NULL THEN flat_time ELSE 0 END) AS flat_time_sum,
    SUM(CASE WHEN flat_dist IS NOT NULL THEN flat_dist ELSE 0 END) AS flat_dist_sum,
    AVG(flat_pace_weather_sec) AS flat_pace_weather_sec
  FROM base
  GROUP BY week, user_id
),
weekly_calc AS (
  SELECT
    week,
    user_id,
    runs,
    distance_m,
    moving_s,
    CASE WHEN distance_m > 0 AND moving_s > 0 THEN moving_s / (distance_m / 1000.0) END AS avg_pace_sec,
    CASE WHEN flat_dist_sum > 0 THEN (flat_time_sum / flat_dist_sum) * 1000.0 END AS flat_pace_sec,
    flat_pace_weather_sec,
    CASE WHEN hr_n > 0 THEN hr_sum / hr_n END AS avg_hr_norm,
    CASE WHEN cadence_n > 0 THEN cadence_sum / cadence_n END AS cadence_avg,
    CASE WHEN speed_n > 0 THEN speed_sum / speed_n END AS avg_speed_mps
  FROM weekly
),
weekly_more AS (
  SELECT
    week,
    user_id,
    runs,
    distance_m,
    moving_s,
    avg_pace_sec,
    flat_pace_sec,
    flat_pace_weather_sec,
    avg_hr_norm,
    cadence_avg,
    CASE WHEN avg_speed_mps IS NOT NULL AND cadence_avg IS NOT NULL AND cadence_avg > 0 THEN (avg_speed_mps * 60.0 / cadence_avg) END AS stride_len,
    CASE WHEN avg_speed_mps IS NOT NULL AND avg_hr_norm IS NOT NULL THEN (avg_speed_mps / avg_hr_norm) END AS eff_index
  FROM weekly_calc
),
weekly_roll AS (
  SELECT
    *,
    AVG(avg_pace_sec) OVER (PARTITION BY user_id ORDER BY week ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS roll_pace_sec,
    AVG(avg_hr_norm) OVER (PARTITION BY user_id ORDER BY week ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS roll_hr,
    AVG(distance_m / 1000.0) OVER (PARTITION BY user_id ORDER BY week ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) AS roll_dist
  FROM weekly_more
),
weeks AS (
  SELECT DISTINCT week, user_id FROM weekly_more
),
days(week, user_id, day) AS (
  SELECT week, user_id, date(week) FROM weeks
  UNION ALL
  SELECT week, user_id, date(day, '+1 day') FROM days WHERE day < date(week, '+6 day')
),
daily AS (
  SELECT
    d.week,
    d.user_id,
    d.day,
    COALESCE(SUM(b.distance_m), 0) AS dist_m
  FROM days d
  LEFT JOIN base b ON date(b.start_time) = d.day AND b.week = d.week AND b.user_id = d.user_id
  GROUP BY d.week, d.user_id, d.day
),
daily_stats AS (
  SELECT
    week,
    user_id,
    AVG(dist_m) AS mean_dist,
    AVG(dist_m * dist_m) AS mean_sq,
    SUM(dist_m) AS load_m
  FROM daily
  GROUP BY week, user_id
),
mono AS (
  SELECT
    week,
    user_id,
    CASE
      WHEN (mean_sq - mean_dist * mean_dist) > 0
      THEN mean_dist / sqrt(mean_sq - mean_dist * mean_dist)
    END AS monotony,
    load_m
  FROM daily_stats
)
SELECT
  w.week,
  w.user_id,
  w.runs,
  w.distance_m,
  w.moving_s,
  w.avg_pace_sec,
  w.flat_pace_sec,
  w.flat_pace_weather_sec,
  w.avg_hr_norm,
  w.cadence_avg,
  w.stride_len,
  w.eff_index,
  w.roll_pace_sec,
  w.roll_hr,
  w.roll_dist,
  m.monotony,
  CASE WHEN m.monotony IS NOT NULL THEN (m.monotony * (m.load_m / 1000.0)) END AS strain
FROM weekly_roll w
LEFT JOIN mono m ON m.week = w.week AND m.user_id = w.user_id;
