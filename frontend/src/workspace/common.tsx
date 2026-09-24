import { useEffect, useRef, useState } from "react";
import { AniRecApiError } from "../api/client";

export function useRead<T>(read: () => Promise<T>, key: string) {
  const current = useRef(read);
  current.current = read;
  const [result, setResult] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setResult(null);
    current.current().then(value => {
      if (!cancelled) setResult(value);
    }).catch((error: unknown) => {
      if (!cancelled) setError(error instanceof AniRecApiError ? `${error.detail.description} ${error.detail.solution}` : "This view could not be loaded. Check the local service and try again.");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [key, attempt]);
  return { result, error, loading, retry: () => setAttempt(x => x + 1) };
}

export function ReadState({ loading, error, retry }: { loading: boolean; error: string; retry: () => void }) {
  if (error) return <div className="workspace-message" role="alert"><p>{error}</p><button className="btn" onClick={retry}>Try again</button></div>;
  return loading ? <p className="workspace-message" role="status">Loading…</p> : null;
}

export function Poster({ title, url }: { title: string; url?: string | null }) {
  const [failed, setFailed] = useState<string | null>(null);
  const valid = url && /^https?:\/\//i.test(url) && failed !== url;
  return <div className="workspace-poster">
    {valid ? <img src={url} alt={`${title} poster`} width={152} height={228} loading="lazy" onError={() => setFailed(url)} />
      : <span role="img" aria-label={`Poster unavailable for ${title}`}><b>{title.split(/\s+/).map(x => x[0]).slice(0, 2).join("")}</b><small>Poster unavailable</small></span>}
  </div>;
}

export const number = (value: number | null | undefined, digits = 0) => value == null || !Number.isFinite(value) ? "N/A" : value.toLocaleString("en-US", { maximumFractionDigits: digits });

export function Scores({ yours, theirs, other = "Community" }: { yours?: number | null; theirs?: number | null; other?: string }) {
  return <dl className="paired-scores"><div><dt>You / 10</dt><dd>{number(yours, 2)}</dd></div><div><dt>{other} / 10</dt><dd>{number(theirs, 2)}</dd></div></dl>;
}

export function Genres({ genres }: { genres: string[] }) {
  return <div className="workspace-genres" aria-label="Genres">{genres.map(genre => <span className="workspace-genre" key={genre}>{genre}</span>)}</div>;
}

/**
 * The desktop's "X // Y" channel legend as the page heading. The page's name
 * is the heading's accessible name; the channel mark after the rule is
 * decoration, hidden from screen readers, and drawn in capitals by CSS.
 */
export function ChannelHeading({ name, mark }: { name: string; mark: string }) {
  return <h1 className="channel-heading" tabIndex={-1}>{name} <span aria-hidden="true">// {mark}</span></h1>;
}

/** 50 per page, the same batch a web refresh generates (D-018). */
export const PAGE_SIZE = 50;

/**
 * Previous / next over what is loaded. With `onLoadMore`, "Next page" on the
 * last loaded page continues the same ranking with the next batch instead of
 * stopping; that replaced the "Recommend 5 more" button (D-018).
 */
export function PageControls({ page, total, onPageChange, label, onLoadMore, loadMoreUnavailable = null, loadingMore = false }: {
  page: number; total: number; onPageChange: (page: number) => void; label: string;
  onLoadMore?: () => void; loadMoreUnavailable?: string | null; loadingMore?: boolean;
}) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const last = page >= pages - 1;
  const continues = last && !!onLoadMore;
  // Nothing shown: the empty state carries the action instead.
  if (total === 0 || (pages <= 1 && !onLoadMore)) return null;
  return <nav className="page-controls" aria-label={`${label} pages`}>
    <button type="button" className="btn" aria-label={`Previous ${label.toLowerCase()} page`} disabled={page === 0} onClick={() => onPageChange(page - 1)}>Previous page</button>
    <span role="status">{loadingMore ? `Loading the next ${PAGE_SIZE} ${label.toLowerCase()}…`
      : `Showing ${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} of ${total} ${label.toLowerCase()} · Page ${page + 1} of ${pages}`}</span>
    {/* The accessible name starts with the visible text (WCAG 2.5.3). */}
    <button type="button" className="btn" aria-label={continues ? `Next page, load the next ${PAGE_SIZE} ${label.toLowerCase()}` : `Next ${label.toLowerCase()} page`}
      title={continues ? loadMoreUnavailable ?? `Continue the same ranking with the next ${PAGE_SIZE}.` : undefined}
      disabled={loadingMore || (continues ? !!loadMoreUnavailable : last)}
      onClick={() => (continues ? onLoadMore!() : onPageChange(page + 1))}>Next page</button>
  </nav>;
}
