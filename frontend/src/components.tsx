import { ApiError } from "./api";

export function Loading() {
  return <p className="muted">Loading…</p>;
}

export function ErrorBox({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const requestId = error instanceof ApiError ? error.requestId : undefined;
  return (
    <div className="error" role="alert">
      <strong>{error.message}</strong>
      {requestId && <div className="muted">Reference: {requestId}</div>}
      {onRetry && <button onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${status.toLowerCase()}`}>{status}</span>;
}

interface PagerProps {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}

export function Pager({ total, limit, offset, onChange }: PagerProps) {
  if (total === 0) return null;
  return (
    <div className="pager">
      <button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
        Previous
      </button>
      <span>
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <button disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>
        Next
      </button>
    </div>
  );
}