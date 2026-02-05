export default function TabNav({ tabs, active, onChange }) {
  return (
    <div className="tab-nav">
      {tabs.map((tab) => (
        <button
          key={tab}
          className={`tab-btn ${active === tab ? 'is-active' : ''}`}
          onClick={() => onChange(tab)}
          type="button"
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
