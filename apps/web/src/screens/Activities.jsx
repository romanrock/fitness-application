import { useEffect, useRef } from 'react';
import ActivityCard from '../components/ActivityCard.jsx';

export default function Activities({ contract, onSelectActivity, onLoadMore, hasMore, loading, error }) {
  const sentinelRef = useRef(null);

  useEffect(() => {
    if (!sentinelRef.current || !hasMore || loading) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) onLoadMore();
      },
      { rootMargin: '200px' }
    );
    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasMore, loading, onLoadMore]);

  return (
    <div className="screen">
      <div className="screen-header">
        <div>
          <h1>{contract.title}</h1>
          <div className="muted">{contract.filterLabel}</div>
        </div>
      </div>

      <div className="section">
        <div className="activity-feed">
          {error && <div className="muted">{error}</div>}
          {contract.items.length ? (
            contract.items.map((activity) => (
              <ActivityCard
                key={activity.id}
                title={activity.title}
                date={activity.date}
                stats={activity.stats}
                accent={activity.accent}
                onClick={() => onSelectActivity(activity)}
              />
            ))
          ) : loading ? (
            <div className="muted">Loading activities…</div>
          ) : (
            <div className="muted">No activities found for this filter.</div>
          )}
        </div>
        <div ref={sentinelRef} className="activity-sentinel">
          {loading && <div className="muted">Loading more…</div>}
          {!hasMore && contract.items.length > 0 && <div className="muted">End of list.</div>}
        </div>
      </div>
    </div>
  );
}
