/**
 * Loading, error and empty.
 *
 * The error panel renders the presentable_error model field for field -
 * title, description, solution, and a retry offered only when the backend
 * said the failure was retryable. That last part matters: the desktop already
 * decides retryability server-side, and a frontend that offered "Try again"
 * on a permanently invalid Client ID would be inviting a person to repeat a
 * request that cannot succeed.
 */

import type { ApiError } from "../api/types";

export function FeedSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div className="feed" aria-busy="true" aria-label="Loading recommendations">
      {Array.from({ length: count }, (_, index) => (
        <div className="skeleton" key={index} style={{ animationDelay: `${index * 0.08}s` }}>
          <div className="art" />
          <div className="line" />
          <div className="line short" />
        </div>
      ))}
    </div>
  );
}

export function ErrorPanel({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div className="state-panel" data-tone="error" role="alert">
      <span className="led off" />
      <h2>{error.title}</h2>
      <p>{error.description}</p>
      {error.solution ? <p className="lbl">{error.solution}</p> : null}
      {error.retryable ? (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function EmptyPanel({
  filtered,
  onClear,
}: {
  filtered: boolean;
  onClear: () => void;
}) {
  return (
    <div className="state-panel">
      <span className="led off" />
      <h2>{filtered ? "No titles match these filters" : "Nothing to show yet"}</h2>
      <p>
        {filtered
          ? "Every recommendation in the feed was excluded by the active filters."
          : "Run an analysis to generate recommendations from your MyAnimeList history."}
      </p>
      {filtered ? (
        <button type="button" className="btn" onClick={onClear}>
          Clear filters
        </button>
      ) : null}
    </div>
  );
}
