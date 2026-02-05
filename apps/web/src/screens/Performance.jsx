import InsightCard from '../components/InsightCard.jsx';

export default function Performance({ contract, onSelectMetric, loading, error }) {
  if (loading) {
    return (
      <div className="screen">
        <div className="muted">Loading performance…</div>
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
          <h1>Performance</h1>
          <div className="muted">Best times and estimates</div>
        </div>
        <button className="icon-btn" type="button">•••</button>
      </div>

      <div className="section">
        <div className="insight-grid">
          {contract.performance.map((item) => (
            <InsightCard
              key={item.id}
              label={item.label}
              value={item.value}
              tone="neutral"
              hint={item.hint}
              onClick={() => onSelectMetric(item)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
