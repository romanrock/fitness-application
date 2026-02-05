import { useLayoutEffect, useRef, useState } from 'react';
import MetricCard from '../components/MetricCard.jsx';
import TabNav from '../components/TabNav.jsx';
import DataTable from '../components/DataTable.jsx';
import ChartCard from '../components/ChartCard.jsx';
import RouteMap from '../components/RouteMap.jsx';

export default function ActivityDetail({ contract, onBack, loading, error }) {
  const [activeTab, setActiveTab] = useState(contract.tabs[0]);
  const lapColumns = [
    { key: 'lap', label: 'Lap' },
    { key: 'time', label: 'Time' },
    { key: 'distance', label: 'Distance' },
    { key: 'pace', label: 'Avg Pace' },
    { key: 'elev', label: 'Elev Δ' },
    { key: 'flat', label: 'Flat Pace' }
  ];

  if (loading) {
    return (
      <div className="screen">
        <div className="muted">Loading activity…</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="screen">
        <button className="icon-btn" onClick={onBack} type="button">←</button>
        <div className="muted">{error}</div>
      </div>
    );
  }
  const notes = contract.summary?.summary_notes || [];
  return (
    <div className="screen">
      <div className="screen-header">
        <button className="icon-btn" onClick={onBack} type="button">←</button>
        <div>
          <h1>{contract.title}</h1>
          <div className="muted">{contract.date} • {contract.location}</div>
          {contract.id && <div className="muted">ID: {contract.id}</div>}
        </div>
        <div className="weather-pill">{contract.weather}</div>
      </div>

      {notes.length > 0 && (
        <div className="section">
          <div className="card">
            {notes.includes('missing_streams') && (
              <div className="muted">No stream data available for this activity.</div>
            )}
            {notes.includes('missing_hr_streams') && (
              <div className="muted">HR stream missing; HR-based stats may be unavailable.</div>
            )}
          </div>
        </div>
      )}

      <div className="hero-card">
        <div className="hero-map">
          <RouteMap points={contract.route || []} />
        </div>
        <div className="hero-metrics">
          {contract.heroStats.map((stat) => (
            <MetricCard key={stat.label} label={stat.label} value={stat.value} accent="run" />
          ))}
        </div>
      </div>

      <TabNav tabs={contract.tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === 'Laps' && (
        <div className="section">
          {contract.laps && contract.laps.length ? (
            <DataTable columns={lapColumns} rows={contract.laps} footer={contract.lapTotals} />
          ) : (
            <div className="muted">Lap data not available yet.</div>
          )}
        </div>
      )}

      {activeTab === 'Charts' && (
        <div className="section chart-grid">
          <ChartCard title="Pace" accent="run" summary={contract.summary?.avg_pace_sec ? formatPace(contract.summary.avg_pace_sec) : '—'}>
            {hasSeriesData(contract.series?.pace) ? (
              <MiniChart
                data={contract.series.pace}
                time={contract.series.time}
                color="run"
                formatValue={formatPace}
                invert
                clipPercentile={0.98}
              />
            ) : (
              <div className="chart-placeholder chart-run"></div>
            )}
          </ChartCard>
          <ChartCard title="Heart Rate" accent="neutral" summary={contract.summary?.avg_hr_norm ? `${Math.round(contract.summary.avg_hr_norm)} bpm` : '—'}>
            {hasSeriesData(contract.series?.hr) ? (
              <MiniChart data={contract.series.hr} time={contract.series.time} color="hr" formatValue={(v) => `${Math.round(v)} bpm`} />
            ) : (
              <div className="chart-placeholder chart-hr"></div>
            )}
          </ChartCard>
          <ChartCard title="Cadence" accent="neutral" summary={contract.summary?.cadence_avg ? `${Math.round(contract.summary.cadence_avg)} spm` : '—'}>
            {hasSeriesData(contract.series?.cadence) ? (
              <MiniChart data={contract.series.cadence} time={contract.series.time} color="cadence" formatValue={(v) => `${Math.round(v)} spm`} />
            ) : (
              <div className="chart-placeholder chart-cadence"></div>
            )}
          </ChartCard>
          <ChartCard title="Elevation" accent="neutral" summary={contract.summary?.elev_gain != null ? `${contract.summary.elev_gain} m` : '—'}>
            {hasSeriesData(contract.series?.elevation) ? (
              <MiniChart data={contract.series.elevation} time={contract.series.time} color="elevation" formatValue={(v) => `${Math.round(v)} m`} />
            ) : (
              <div className="chart-placeholder chart-elevation"></div>
            )}
          </ChartCard>
          <ChartCard title="Time in Heart Rate Zones" accent="neutral" summary={contract.summary?.hr_zone_label ? `${contract.summary.hr_zone_label}` : '—'}>
            {contract.summary?.hr_zones?.length ? (
              <ZonesBreakdown zones={contract.summary.hr_zones} />
            ) : (
              <div className="muted">Zone data not available.</div>
            )}
          </ChartCard>
        </div>
      )}

      {activeTab === 'Overview' && (
        <div className="section">
          <ChartCard title="Key Stats" accent="run">
            <div className="stats-list">
              <div className="stats-row"><span>Avg Pace</span><span>{contract.summary?.avg_pace_sec ? formatPace(contract.summary.avg_pace_sec) : '—'}</span></div>
              <div className="stats-row"><span>Avg Flat Pace</span><span>{contract.summary?.flat_pace_sec ? formatPace(contract.summary.flat_pace_sec) : '—'}</span></div>
              <div className="stats-row"><span>Best Pace</span><span>{contract.summary?.best_pace_sec ? formatPace(contract.summary.best_pace_sec) : '—'}</span></div>
              <div className="stats-row"><span>Moving Time</span><span>{contract.summary?.moving_s ? formatTime(contract.summary.moving_s) : '—'}</span></div>
              <div className="stats-row"><span>Avg HR (norm)</span><span>{contract.summary?.avg_hr_norm ? `${Math.round(contract.summary.avg_hr_norm)} bpm` : '—'}</span></div>
              <div className="stats-row"><span>Avg HR (raw)</span><span>{contract.summary?.avg_hr_raw ? `${Math.round(contract.summary.avg_hr_raw)} bpm` : '—'}</span></div>
              <div className="stats-row"><span>Cadence</span><span>{contract.summary?.cadence_avg ? `${Math.round(contract.summary.cadence_avg)} spm` : '—'}</span></div>
              <div className="stats-row"><span>Avg Stride Length</span><span>{contract.summary?.stride_len ? `${contract.summary.stride_len.toFixed(2)} m` : '—'}</span></div>
              <div className="stats-row"><span>Calories</span><span>{contract.summary?.calories != null ? `${contract.summary.calories}` : '—'}</span></div>
              <div className="stats-row">
                <span>Zone Score (weights 1–5)</span>
                <span>{contract.summary?.hr_zone_score ? `${contract.summary.hr_zone_score.toFixed(2)} • ${contract.summary.hr_zone_label || ''}` : '—'}</span>
              </div>
            </div>
          </ChartCard>
          <ChartCard title="Segments" accent="run">
            <SegmentsTable segments={contract.segments} activitySegments={contract.activitySegments} />
          </ChartCard>
        </div>
      )}
    </div>
  );
}

function MiniChart({ data, time, color, formatValue, invert = false, clipPercentile = 1 }) {
  const [canvasRef, size] = useChartSize();
  const width = size.width || 420;
  const height = size.height || 220;
  const padTop = 10;
  const padBottom = 10;
  const innerWidth = width;
  const innerHeight = Math.max(1, height - padTop - padBottom);
  const clean = data.filter((v) => v != null);
  if (!clean.length) {
    return (
      <div className="mini-chart-wrap">
        <div className="chart-placeholder chart-empty" />
      </div>
    );
  }
  const sorted = clean.slice().sort((a, b) => a - b);
  const clipIndex = Math.max(0, Math.floor(sorted.length * clipPercentile) - 1);
  const clipMax = sorted[clipIndex] ?? Math.max(...clean);
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const displayMax = clipPercentile < 1 ? clipMax : max;
  const range = max - min || 1;
  const displayRange = displayMax - min || 1;
  const points = data
    .map((v, i) => {
      if (v == null) return null;
      const x = (i / (data.length - 1)) * innerWidth;
      const clamped = Math.min(v, displayMax);
      const norm = (clamped - min) / displayRange;
      const y = padTop + (invert ? norm * innerHeight : innerHeight - norm * innerHeight);
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(' ');

  const avg = clean.reduce((s, v) => s + v, 0) / (clean.length || 1);
  const avgNorm = (Math.min(avg, displayMax) - min) / displayRange;
  const avgY = padTop + (invert ? avgNorm * innerHeight : innerHeight - avgNorm * innerHeight);
  const avgPct = avgY / height;

  const [hover, setHover] = useState(null);

  const gradient = color === 'hr'
    ? ['#ef4444', '#7f1d1d']
    : color === 'cadence'
      ? ['#a855f7', '#4c1d95']
      : color === 'elevation'
        ? ['#22c55e', '#14532d']
        : ['#0ea5e9', '#1e3a8a'];

  const yTicks = [displayMax, (displayMax + min) / 2, min];
  const yTickMeta = yTicks.map((val) => {
    const yNorm = (val - min) / displayRange;
    const y = padTop + (invert ? yNorm * innerHeight : innerHeight - yNorm * innerHeight);
    return { value: val, pct: y / height };
  });
  const t0 = time && time.length ? time[0] : null;
  const t1 = time && time.length ? time[time.length - 1] : null;
  const tickFractions = [0, 0.25, 0.5, 0.75, 1];
  const tickLabels = tickFractions.map((f) => {
    if (t0 == null || t1 == null) return '—';
    const t = t0 + (t1 - t0) * f;
    return formatTime(t);
  });

  return (
    <div className="mini-chart-wrap">
      <div className="chart-plot">
        <div className="chart-yaxis">
          {yTickMeta.map((tick, idx) => (
            <div className="chart-yaxis__label" style={{ top: `${tick.pct * 100}%` }} key={idx}>
              {formatValue ? formatValue(tick.value) : tick.value.toFixed(1)}
            </div>
          ))}
        </div>
        <div className="chart-canvas" ref={canvasRef}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="mini-chart"
            preserveAspectRatio="none"
            style={{ width: '100%', height: '100%', display: 'block' }}
            onMouseMove={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const x = e.clientX - rect.left;
              const idx = Math.round((x / rect.width) * (data.length - 1));
              const value = data[idx];
              if (value == null) return setHover(null);
              setHover({ idx, value, x: (idx / (data.length - 1)) * innerWidth });
            }}
            onMouseLeave={() => setHover(null)}
          >
        <defs>
          <linearGradient id={`grad-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={gradient[0]} stopOpacity="0.6" />
            <stop offset="100%" stopColor={gradient[1]} stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <polyline points={points} fill="none" stroke={gradient[0]} strokeWidth="2" />
        <polygon points={`0,${padTop + innerHeight} ${points} ${innerWidth},${padTop + innerHeight}`} fill={`url(#grad-${color})`} />
        <line x1={0} y1={avgY} x2={innerWidth} y2={avgY} stroke={gradient[0]} strokeWidth="1" opacity="0.45" strokeDasharray="4 4" />
        {yTickMeta.map((tick, idx) => (
          <line
            key={idx}
            x1={0}
            y1={tick.pct * height}
            x2={innerWidth}
            y2={tick.pct * height}
            stroke="#1a1a1a"
            strokeWidth="1"
            opacity="0.5"
          />
        ))}
        {hover && (() => {
          const clamped = Math.min(hover.value, displayMax);
          const norm = (clamped - min) / displayRange;
          const y = padTop + (invert ? norm * innerHeight : innerHeight - norm * innerHeight);
          return (
            <>
              <line x1={hover.x} y1={padTop} x2={hover.x} y2={padTop + innerHeight} stroke="#ffffff55" strokeWidth="1" />
              <circle cx={hover.x} cy={y} r="3" fill={gradient[0]} />
            </>
          );
        })()}
          </svg>
          <div className="chart-avg-label" style={{ top: `${avgPct * 100}%` }}>
            {formatValue ? formatValue(avg) : avg.toFixed(1)}
          </div>
        </div>
      </div>
      {hover && (
        <div className="chart-tooltip" style={{ left: `${(hover.x / width) * 100}%` }}>
          {formatValue ? formatValue(hover.value) : hover.value.toFixed(1)}
        </div>
      )}
      <div className="chart-axis">
        {tickLabels.map((label, idx) => (
          <div className="chart-axis__tick" key={idx}>
            <span className="chart-axis__dot" />
            <span>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function useChartSize() {
  const ref = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return [ref, size];
}

function SegmentsTable({ segments, activitySegments }) {
  const distances = [400, 800, 1000, 1500, 3000, 5000, 10000];
  const bestAll = segments?.best_all || {};
  const best12w = segments?.best_12w || {};
  const activityBest = activitySegments || {};
  return (
    <div className="segments-grid">
      <div className="segments-row segments-header">
        <div className="segments-dist">Distance</div>
        <div className="segments-cell">
          <div className="segments-label">This run</div>
        </div>
        <div className="segments-cell">
          <div className="segments-label">Best</div>
        </div>
      </div>
      {distances.map((dist) => {
        const all = bestAll[dist];
        const recent = best12w[dist];
        const run = activityBest[dist];
        return (
          <div className="segments-row" key={dist}>
            <div className="segments-dist">{dist >= 1000 ? `${dist / 1000} km` : `${dist} m`}</div>
            <div className="segments-cell">
              <div className="segments-value">{run ? formatTime(run) : '—'}</div>
              <div className="segments-date"> </div>
            </div>
            <div className="segments-cell">
              <div className="segments-value">{all?.time_s ? formatTime(all.time_s) : '—'}</div>
              <div className="segments-date">{all?.date ? String(all.date).slice(0, 10) : '—'}</div>
              <div className="segments-subtle">12w: {recent?.time_s ? formatTime(recent.time_s) : '—'} {recent?.date ? `(${String(recent.date).slice(0, 10)})` : ''}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function hasSeriesData(series) {
  return Array.isArray(series) && series.some((v) => v != null);
}

function ZonesBreakdown({ zones }) {
  return (
    <div className="zones-list">
      {zones.map((zone) => (
        <div className="zones-row" key={zone.zone}>
          <div className="zones-meta">
            <div className="zones-title">Zone {zone.zone}</div>
            <div className="zones-range">{Math.round(zone.low)}–{Math.round(zone.high)} bpm</div>
          </div>
          <div className="zones-bar">
            <div className="zones-bar__fill" style={{ width: `${Math.max(0, Math.min(100, zone.pct || 0))}%` }} />
          </div>
          <div className="zones-values">
            <div className="zones-time">{zone.seconds != null ? formatTime(zone.seconds) : '—'}</div>
            <div className="zones-pct">{zone.pct != null ? `${Math.round(zone.pct)}%` : '—'}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatPace(secPerKm) {
  const m = Math.floor(secPerKm / 60);
  const s = Math.round(secPerKm % 60);
  return `${m}:${String(s).padStart(2, '0')} /km`;
}
