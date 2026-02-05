export default function Profile({ contract }) {
  return (
    <div className="screen">
      <div className="screen-header">
        <div>
          <h1>Profile</h1>
          <div className="muted">Key stats used for performance metrics.</div>
        </div>
      </div>
      <div className="section">
        <div className="card profile-card">
          <div className="profile-title">{contract.name}</div>
          <div className="profile-grid">
            {contract.stats.map((stat) => (
              <div className="profile-item" key={stat.label}>
                <div className="profile-label">{stat.label}</div>
                <div className="profile-value">{stat.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
