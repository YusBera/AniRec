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
