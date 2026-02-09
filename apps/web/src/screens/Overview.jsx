import MetricCard from '../components/MetricCard.jsx';
import InsightCard from '../components/InsightCard.jsx';

export default function Overview({ contract, onSelectActivityType, onSelectInsight, lastUpdate, loading, error, onOpenAssistant }) {
  if (loading) {
    return (
      <div className="screen">
        <div className="muted">Loading dashboard…</div>
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
          <h1>Dashboard</h1>
          <div className="muted">This Week: {contract.weekLabel}</div>
          {lastUpdate && <div className="muted">Last updated: {lastUpdate}</div>}
        </div>
        <button className="icon-btn" type="button" onClick={onOpenAssistant}>Assistant</button>
      </div>

      <div className="section">
        <div className="section-header">
          <h2>All Time</h2>
        </div>
        <div className="metric-grid">
          {contract.allTimeCards.map((card) => (
            <MetricCard
              key={card.id}
              label={card.label}
              value={card.value}
              accent={card.accent}
              onClick={() => onSelectActivityType(card.id, 'all')}
            />
          ))}
        </div>
      </div>

      <div className="section">
        <div className="section-header">
          <h2>This Week</h2>
        </div>
        <div className="metric-grid">
          {contract.weeklyCards.map((card) => (
            <MetricCard
              key={card.id}
              label={card.label}
              value={card.value}
              accent={card.accent}
              onClick={() => onSelectActivityType(card.id, 'week')}
            />
          ))}
        </div>
      </div>

      <div className="section">
        <div className="section-header">
          <h2>Fitness Insights</h2>
        </div>
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

      <div className="section">
        <div className="section-header">
          <h2>Performance (5K / 10K)</h2>
        </div>
        <div className="insight-grid">
          {contract.performance.map((item) => (
            <InsightCard
              key={item.id}
              label={item.label}
              value={item.value}
              tone="neutral"
              hint={item.hint}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
