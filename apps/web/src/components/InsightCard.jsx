export default function InsightCard({ label, value, hint, tone = 'neutral', tooltip, onClick }) {
  return (
    <div className={`insight-card tone-${tone} ${onClick ? 'is-clickable' : ''}`} role={onClick ? 'button' : undefined} tabIndex={onClick ? 0 : undefined} onClick={onClick}>
      <div className="insight-label">
        <span>{label}</span>
        {tooltip && (
          <span className="insight-info" aria-label="Metric details">
            ⓘ
            <span className="insight-tooltip">
              <strong>{tooltip.summary}</strong>
              <span>{tooltip.calc}</span>
              <span><em>Improving:</em> {tooltip.improve}</span>
            </span>
          </span>
        )}
      </div>
      <div className="insight-value">{value}</div>
      {hint && <div className="insight-hint">{hint}</div>}
    </div>
  );
}
