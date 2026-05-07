export interface QueueCounts {
  processing: number;
  queued: number;
}

export function AppHeader({
  connected,
  reconnecting,
  queueCounts,
  onQueueClick,
  showBackLink = false
}: {
  connected: boolean;
  reconnecting: boolean;
  queueCounts: QueueCounts;
  onQueueClick?: () => void;
  showBackLink?: boolean;
}) {
  const goHome = () => {
    window.history.pushState(null, "", "/");
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  return (
    <header className="app-header">
      <div className="header-left">
        {showBackLink ? (
          <button className="back-link" type="button" onClick={goHome}>
            ← Back to list
          </button>
        ) : (
          <button className="brand" type="button" onClick={goHome}>
            <BrandMark />
            <span>Podcast Summary</span>
          </button>
        )}
      </div>
      <div className="header-actions">
        <span
          className={`connection-dot ${connected ? "connection-dot--connected" : reconnecting ? "connection-dot--warn" : ""}`}
          title={connected ? "Realtime connected" : "Realtime reconnecting"}
        />
        {queueCounts.processing + queueCounts.queued > 0 ? (
          <button className="queue-badge" type="button" onClick={onQueueClick}>
            <span aria-hidden="true">∞</span>
            Queue
            <strong>{queueCounts.processing}</strong>
            <span>running</span>
            <strong>{queueCounts.queued}</strong>
            <span>waiting</span>
          </button>
        ) : null}
      </div>
    </header>
  );
}

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span />
      <span />
      <span />
      <span />
    </span>
  );
}
