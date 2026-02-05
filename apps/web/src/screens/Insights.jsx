import InsightCard from '../components/InsightCard.jsx';

export default function Insights({ contract, onSelectInsight, loading, error }) {
  if (loading) {
    return (
      <div className="screen">
        <div className="muted">Loading insights…</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="screen">
        <div className="muted">{error}</div>
      </div>
    );
  }
  return (
    <div className="screen">
      <div className="screen-header">
        <div>
          <h1>Insights</h1>
          <div className="muted">All insight metrics · last 12 months (weekly)</div>
        </div>
        <button className="icon-btn" type="button">•••</button>
      </div>

      <div className="section">
        <div className="insight-grid">
          {contract.insights.map((item) => (
            <InsightCard
              key={item.id}
              label={item.label}
              value={item.value}
              tone={item.tone}
              hint={item.hint}
              tooltip={item.tooltip}
              onClick={() => onSelectInsight(item)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
