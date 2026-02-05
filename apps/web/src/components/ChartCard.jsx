export default function ChartCard({ title, accent = 'run', summary, children }) {
  return (
    <div className={`card chart-card accent-${accent}`}>
      <div className="chart-card__header">
        <div className="chart-card__title">{title}</div>
        {summary && <div className="chart-card__summary">{summary}</div>}
      </div>
      <div className="chart-card__body">{children}</div>
    </div>
  );
}
