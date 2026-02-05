# Metrics Reference

This document describes the metrics currently computed in the fitness-platform, how they are calculated, and what they mean.

## Data Layers
- **Raw**: `activities_raw`, `streams_raw`, `weather_raw`
- **Calculated**: `activities_calc`, `activity_details_run`, `activities_norm`
- **View**: `metrics_weekly` (weekly rollups)

## Per-Activity Metrics

### Distance (distance_m)
- **Source**: Strava activity data.
- **Meaning**: Total distance in meters.

### Moving time (moving_s)
- **Source**: Strava activity data.
- **Meaning**: Total moving time in seconds.

### Avg pace (avg_pace_sec)
- **Formula**: `moving_s / (distance_m / 1000)`
- **Meaning**: Average pace in seconds per km.

### Flat pace (flat_pace_sec)
- **Formula**: Grade-adjusted pace using altitude stream.
- **Details**: For each segment:
  - `grade = clamp((alt[i] - alt[i-1]) / (dist[i] - dist[i-1]), -0.1, 0.1)`
  - `cost = 1 + 0.045*grade + 0.35*grade^2`
  - `flat_sec_per_m = (dt/dd) * cost`
  - Aggregate to flat pace per km.
- **Meaning**: Estimated pace if terrain were flat.

### Flat pace (weather-adjusted) (flat_pace_weather_sec)
- **Formula**: `flat_pace_sec * weather_factor`
- **Weather factor**:
  - If temp > 18°C: `+0.5%` per °C above 18
  - If temp < 5°C: `+0.3%` per °C below 5
  - Wind > 18 km/h: `+0.3%` per km/h above 18
- **Meaning**: Flat pace adjusted for temperature/wind.

### Avg heart rate (raw) (avg_hr_raw)
- **Source**: Strava heartrate stream.
- **Meaning**: Mean HR from raw stream.

### Avg heart rate (normalized) (avg_hr_norm)
- **Source**: Normalized HR stream.
- **Meaning**: Mean HR after normalization to reduce early spikes.

### HR drift (hr_drift)
- **Formula**: `HR(last 25%) - HR(first 25%)`
- **Meaning**: Cardiovascular drift during the run.

### Decoupling (decoupling)
- **Formula**: `((pace2 / pace1) / (hr2 / hr1) - 1) * 100`
- **Robust method**:
  - Split run into first/second half by **distance**.
  - Compute **trimmed mean** (10% trim) for pace and HR in each half.
  - Clamp result to ±50% to avoid extreme outliers.
- **Meaning**: Efficiency change over time; closer to 0 is better.

### Cadence (cadence_avg)
- **Source**: Strava cadence stream.
- **Meaning**: Steps per minute average.

### Stride length (stride_len)
- **Formula**: `(avg_speed_mps * 60) / cadence_avg`
- **Meaning**: Estimated meters per step.

### Calories (calories)
- **Source**: Strava calories if available; else kilojoules * 0.239006; else estimated.
- **Estimate fallback**: `distance_km * weight_kg` (weight from `FITNESS_WEIGHT_KG`, default 75).
- **Meaning**: Estimated energy expenditure.

### Best pace (best_pace_sec)
- **Formula**: Minimum of smoothed pace series (150–900 sec/km range).
- **Meaning**: Fastest pace sample after smoothing.

### HR zones (hr_z1_s .. hr_z5_s)
- **Method**: Heart‑rate reserve (Karvonen).
- **Inputs**: `HR_max` and `HR_rest` (defaults from env `FITNESS_HR_MAX=185`, `FITNESS_HR_REST=48`).
- **Formula**:
  - `HRR = HR_max - HR_rest`
  - Zone boundaries:
    - Z1: 50–60% HRR
    - Z2: 60–70% HRR
    - Z3: 70–80% HRR
    - Z4: 80–90% HRR
    - Z5: 90–100% HRR
  - `HR_at_% = HR_rest + % * HRR`
- **Computation**:
  - Use normalized HR stream where available (fallback to raw).
  - Accumulate seconds per zone using the time stream (`dt = time[i]-time[i-1]`).
- **Meaning**: Time spent in each training intensity zone.

### HR zone score (hr_zone_score) + label (hr_zone_label)
- **Formula**: `Σ(zone_seconds * zone_weight) / total_seconds`, with weights Z1=1 .. Z5=5.
- **Labels**:
  - `<1.5` Recovery
  - `<2.5` Endurance
  - `<3.5` Tempo
  - `<4.5` Threshold
  - `>=4.5` VO2
- **Meaning**: Simple intensity score for the run based on zone distribution.

### Route (route polyline)
- **Source**: Strava map polyline.
- **Meaning**: Encoded path for map rendering.

### Laps
- **Lap time**: delta of time stream between lap markers.
- **Lap pace**: `lap_time / (lap_distance_km)`
- **Lap elevation change**: `alt[end] - alt[start]`
- **Lap flat pace**: same grade-adjusted method over lap segment.

## Weekly Rollup Metrics (`metrics_weekly`)

### Runs
- **Formula**: count of run activities per week.

### Distance
- **Formula**: sum of distance_m.

### Avg pace
- **Formula**: `sum(moving_s) / (sum(distance_m)/1000)`

### Flat pace
- **Formula**: weighted by `flat_time / flat_dist`.

### Avg HR (norm)
- **Formula**: mean of per-activity HR (raw or norm when available).

### Cadence avg
- **Formula**: mean cadence over week.

### Stride length
- **Formula**: `(avg_speed_mps * 60) / cadence_avg`

### Efficiency index (eff_index)
- **Formula**: `avg_speed_mps / avg_hr_norm`
- **Meaning**: Higher suggests better efficiency.

### Rolling pace/HR/distance
- **Formula**: 4-week trailing averages.

### Monotony
- **Formula**: `mean daily load / stddev daily load`
- **Meaning**: Higher monotony indicates less variation.

### Strain
- **Formula**: `monotony * (weekly distance in km)`
- **Meaning**: Training strain proxy.

## Fitness Insights (Dashboard)

### VDOT (best 12 months)
- **Formula**: Daniels VDOT estimate from best recent run (distance ≥ 5K) in last 12 months.
- **Details**:
  - `v_m_min = (distance_m / moving_s) * 60`
  - `VO2 = -4.60 + 0.182258*v + 0.000104*v^2`
  - `%VO2max = 0.8 + 0.1894393*e^{-0.012778*t} + 0.2989558*e^{-0.1932605*t}`
  - `VDOT = VO2 / %VO2max`
- **Meaning**: Performance-based fitness estimate (not a lab test).

### Pace trend (12 weeks)
- **Formula**: Linear slope of `avg_pace_sec` over last 12 weekly points.
- **Meaning**: Negative values indicate improving pace.

### HR trend (12 weeks)
- **Formula**: Linear slope of `avg_hr_norm` over last 12 weekly points.
- **Meaning**: Negative values indicate lower HR cost over time.

### Efficiency trend (12 weeks)
- **Formula**: Linear slope of `eff_index` over last 12 weekly points.
- **Meaning**: Positive values indicate improving efficiency.

### Decoupling (28 days)
- **Formula**: Mean of per-activity `decoupling` over last 28 days.
- **Meaning**: Closer to 0 is better (less drift between pace and HR).

### HR drift (28 days)
- **Formula**: Mean of per-activity `hr_drift` over last 28 days.
- **Meaning**: Lower is better (less HR rise over time).

### Run volume (7d / 28d)
- **Formula**: Sum of run `distance_m` in last 7 and 28 days.
- **Meaning**: Training volume snapshot.

### PB 5K / 10K (all time)
- **Source**: `segments_best` (scope `best_all`) for 5000m / 10000m.
- **Meaning**: Best time achieved for those distances using segment search.

### PB 5K / 10K (last 12 months)
- **Source**: Best full-activity pace from runs in last 12 months with distance ≥ 5K / 10K.
- **Meaning**: Best recent full-run performance.

### Segment-based estimates (5K / 10K)
- **Source**: `segments_best` from Strava Local ingest.
- **Method**: Riegel projection from best segment (prefer 3K, else 5K or 10K).
- **Formula**: `T2 = T1 * (D2 / D1)^1.06`
- **Meaning**: Estimated potential time from strongest segment.

### Best segments (400–10,000)
- **Source**: `segments_best` for distances 400, 800, 1000, 1500, 3000, 5000, 10000.
- **Scopes**:
  - `best_all`: all-time bests.
  - `best_12w`: bests over last 12 weeks.

## Notes
- All metrics currently use **run** activities only for weekly views.
- Weather adjustment uses limited heuristics; can be refined later.
- Normalized HR and smoothed pace/cadence are computed in processing step.
