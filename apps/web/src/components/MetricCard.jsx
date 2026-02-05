export default function MetricCard({ label, value, accent = 'neutral', icon, onClick }) {
  return (
    <button className={`card metric-card accent-${accent}`} type="button" onClick={onClick} disabled={!onClick}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {icon && <div className="metric-icon">{icon}</div>}
    </button>
  );
}
