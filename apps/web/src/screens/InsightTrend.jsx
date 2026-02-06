import { useEffect, useMemo, useState } from 'react';
import ChartCard from '../components/ChartCard.jsx';

export default function InsightTrend({ insight, onBack, apiFetch }) {
  const [series, setSeries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [seriesMeta, setSeriesMeta] = useState(null);

  useEffect(() => {
    if (!insight?.id) return;
    setLoading(true);
    setError(null);
    const fetcher = apiFetch
      ? () => apiFetch(`/insights/series?metric=${encodeURIComponent(insight.id)}&weeks=52`)
      : () => fetch(`/api/v1/insights/series?metric=${encodeURIComponent(insight.id)}&weeks=52`);
    fetcher()
      .then((r) => r.json())
      .then((data) => {
        setSeries(data.series || []);
        setSeriesMeta(data.series_meta || null);
      })
      .catch(() => setError('Failed to load trend.'))
      .finally(() => setLoading(false));
  }, [insight?.id]);

  const values = useMemo(
    () => series.map((p) => p.value).filter((v) => v != null),
    [series]
  );

  return (
    <div className="screen">
      <div className="screen-header">
        <div>
          <h1>{insight?.label || 'Metric Trend'}</h1>
          <div className="muted">Last 12 months · weekly</div>
        </div>
        <button className="icon-btn" type="button" onClick={onBack}>Back</button>
      </div>

      <div className="section">
        <ChartCard title={insight?.label || 'Trend'} accent="run" summary={insight?.value}>
          <div className="insight-trend">
            {loading ? (
              <div className="chart-placeholder" />
            ) : error ? (
              <div className="muted">{error}</div>
            ) : seriesMeta?.reason === 'missing_hr_streams' ? (
              <div className="muted">HR stream data missing. Unable to compute this metric.</div>
            ) : seriesMeta?.reason === 'no_data' ? (
              <div className="muted">No data available for this metric yet.</div>
            ) : values.length === 0 ? (
              <div className="chart-placeholder chart-empty" />
            ) : (
              <InsightTrendChart series={series} />
            )}
          </div>
        </ChartCard>
      </div>

      {insight?.tooltip && (
        <div className="section">
          <div className="card">
            <h3 className="muted">About this metric</h3>
            <p>{insight.tooltip.summary}</p>
            <p><strong>Calculation:</strong> {insight.tooltip.calc}</p>
            <p><strong>Improving:</strong> {insight.tooltip.improve}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function InsightTrendChart({ series }) {
  const [hover, setHover] = useState(null);
  const width = 720;
  const height = 260;
  const padLeft = 48;
  const padRight = 16;
  const padTop = 16;
  const padBottom = 32;
  const innerWidth = width - padLeft - padRight;
  const innerHeight = height - padTop - padBottom;

  const values = series.map((p) => p.value).filter((v) => v != null);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = series.map((p, i) => {
    if (p.value == null) return null;
    const x = padLeft + (i / (series.length - 1)) * innerWidth;
    const y = padTop + innerHeight - ((p.value - min) / range) * innerHeight;
    return `${x},${y}`;
  }).filter(Boolean).join(' ');

  const avg = values.reduce((s, v) => s + v, 0) / values.length;
  const avgY = padTop + innerHeight - ((avg - min) / range) * innerHeight;

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => {
    const idx = Math.round((series.length - 1) * f);
    return { x: padLeft + f * innerWidth, label: series[idx]?.week || '' };
  });
  const yTicks = [max, (max + min) / 2, min];

  return (
    <div className="insight-trend__wrap">
      <svg
        className="insight-trend__svg"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const idx = Math.round((x / rect.width) * (series.length - 1));
          const point = series[idx];
          if (!point || point.value == null) {
            setHover(null);
            return;
          }
          const cx = padLeft + (idx / (series.length - 1)) * innerWidth;
          const cy = padTop + innerHeight - ((point.value - min) / range) * innerHeight;
          setHover({ ...point, x: cx, y: cy });
        }}
        onMouseLeave={() => setHover(null)}
      >
      <defs>
        <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0.05" />
        </linearGradient>
      </defs>

      {yTicks.map((v, i) => {
        const y = padTop + innerHeight - ((v - min) / range) * innerHeight;
        return (
          <g key={i}>
            <line x1={padLeft} y1={y} x2={width - padRight} y2={y} stroke="#1d1d1f" strokeWidth="1" />
            <text x={8} y={y + 4} fill="#9ca3af" fontSize="10">{formatValue(v)}</text>
          </g>
        );
      })}

      <line x1={padLeft} y1={avgY} x2={width - padRight} y2={avgY} stroke="#22c55e" strokeWidth="1" strokeDasharray="4 4" />

      <polyline points={points} fill="none" stroke="#0ea5e9" strokeWidth="2" />
      <polygon points={`${padLeft},${padTop + innerHeight} ${points} ${width - padRight},${padTop + innerHeight}`} fill="url(#trend-fill)" />

      {xTicks.map((t, i) => (
        <text key={i} x={t.x} y={height - 10} textAnchor="middle" fill="#9ca3af" fontSize="10">
          {t.label}
        </text>
      ))}
      {hover && (
        <>
          <line x1={hover.x} y1={padTop} x2={hover.x} y2={padTop + innerHeight} stroke="#ffffff55" strokeWidth="1" />
          <circle cx={hover.x} cy={hover.y} r="3" fill="#0ea5e9" />
        </>
      )}
      </svg>
      {hover && (
        <div className="insight-trend__tooltip" style={{ left: `${(hover.x / width) * 100}%` }}>
          <div className="insight-trend__tooltip-label">{hover.week}</div>
          <div className="insight-trend__tooltip-value">{formatValue(hover.value)}</div>
        </div>
      )}
    </div>
  );
}

function formatValue(value) {
  if (value == null || Number.isNaN(value)) return '—';
  if (Math.abs(value) >= 1000) return value.toFixed(0);
  if (Math.abs(value) >= 10) return value.toFixed(1);
  return value.toFixed(2);
}
