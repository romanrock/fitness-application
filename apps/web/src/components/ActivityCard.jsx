export default function ActivityCard({ title, date, stats, accent = 'neutral', onClick }) {
  return (
    <button className={`card activity-card accent-${accent}`} onClick={onClick} type="button">
      <div className="activity-card__header">
        <div className="activity-card__title">{title}</div>
        <div className="activity-card__date">{date}</div>
      </div>
      <div className="activity-card__stats">
        {stats.map((stat, idx) => (
          <div key={idx} className="activity-card__stat">{stat}</div>
        ))}
      </div>
    </button>
  );
}
