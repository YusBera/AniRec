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

import type { ReactNode } from "react";
import type { ApiError } from "../api/types";
import { Icon, type IconName } from "../assets/Icon";

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

/**
 * An empty collection or feed, as `_show_current_view` words each case: a
 * folder or search mark, a title, one sentence, and the way out.
 */
export function EmptyPanel({ icon, title, message, children }: {
  icon: IconName;
  title: string;
  message: string;
  children?: ReactNode;
}) {
  return (
    <div className="state-panel empty-panel">
      <Icon name={icon} className="empty-icon" />
      <h2>{title}</h2>
      <p>{message}</p>
      {children ? <div className="empty-actions">{children}</div> : null}
    </div>
  );
}
