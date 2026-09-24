/**
 * Two hooks: one that loads the feed, one that follows an operation.
 *
 * Hand-written rather than TanStack Query. For a single surface that is about
 * forty lines against a dependency, and writing it makes the comparison at the
 * decision gate honest - the React side is not winning because a library did
 * the work. At three surfaces the answer flips: shared cache keys,
 * deduplication and background refetch are exactly what Query exists for, and
 * re-deriving them by hand would be the mistake.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AniRecApiError, api } from "./client";
import type { ApiError, Feed, OperationState, ProgressEvent } from "./types";

export type LoadState = "idle" | "loading" | "ready" | "error";

export function useFeed(includeHidden = false) {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<ApiError | null>(null);

  // Only the newest read may land: a superseded response carries a whole
  // local state that could revert a decision saved after it was served.
  const latest = useRef(0);
  const load = useCallback(async (options?: { quiet?: boolean }) => {
    const request = ++latest.current;
    if (!options?.quiet) setState("loading");
    try {
      const next = await api.feed(includeHidden);
      if (request !== latest.current) return;
      setFeed(next);
      setError(null);
      setState("ready");
    } catch (caught) {
      if (request !== latest.current) return;
      if (caught instanceof AniRecApiError) setError(caught.detail);
      setState("error");
    }
  }, [includeHidden]);

  useEffect(() => {
    void load();
  }, [load]);

  return { feed, state, error, reload: load, setFeed };
}

export interface OperationProgress {
  id: string | null;
  /** The operation kind this client started, e.g. "recommendation". */
  kind: string | null;
  state: OperationState | "idle";
  progress: ProgressEvent | null;
  error: ApiError | null;
}

const IDLE: OperationProgress = { id: null, kind: null, state: "idle", progress: null, error: null };

/** The progress stream closed before the operation reported an outcome. */
const LOST_STREAM: ApiError = {
  code: "stream_lost",
  title: "Lost contact with the running operation",
  description: "The progress stream closed before the operation finished, so its outcome is unknown.",
  solution: "Reload the page to see the current recommendations.",
  retryable: true,
};

/**
 * `OperationAlreadyRunningError` arrives as a 409 whose description starts
 * "Operation is already running". It is not a failed request, so it is worded
 * as what it is, with the service's own sentence kept. Other 409s (no active
 * profile, the profile changed) keep the service's wording unchanged.
 */
function startError(caught: unknown): ApiError {
  if (caught instanceof AniRecApiError && caught.status === 409 && /already running/i.test(caught.detail.description)) {
    return {
      ...caught.detail,
      title: "Another operation is already running",
      solution: "Wait for it to finish, then try again.",
      retryable: false,
    };
  }
  return caught instanceof AniRecApiError ? caught.detail : {
    code: "network_error",
    title: "The operation could not be started",
    description: "The request did not complete.",
    solution: "Confirm the AniRec service is running, then try again.",
    retryable: true,
  };
}

/**
 * Start an operation and follow its event stream to a terminal state.
 *
 * The stream replays from the beginning, so a component that mounts its
 * EventSource after the POST returns still sees `started` and every progress
 * event. That replay is what makes the HTTP version equivalent to Qt signals
 * rather than lossy: a Qt client connects its slots before the worker runs and
 * cannot miss anything, an HTTP client always connects late.
 */
export function useOperation(onFinished?: (state: OperationState) => void) {
  const [status, setStatus] = useState<OperationProgress>(IDLE);
  const sourceRef = useRef<EventSource | null>(null);
  const finishedRef = useRef(onFinished);
  finishedRef.current = onFinished;

  const close = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  useEffect(() => close, [close]);

  const start = useCallback(
    async (kind: string, payload: Record<string, unknown> = {}) => {
      close();
      setStatus({ ...IDLE, kind, state: "running" });
      let snapshot;
      try {
        snapshot = await api.startOperation(kind, payload);
      } catch (caught) {
        setStatus({ id: null, kind, state: "failed", progress: null, error: startError(caught) });
        return null;
      }

      const source = new EventSource(api.eventsUrl(snapshot.id));
      sourceRef.current = source;
      setStatus((current) => ({ ...current, id: snapshot.id }));

      source.addEventListener("progress", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as ProgressEvent;
        setStatus((current) => ({ ...current, progress: data }));
      });
      source.addEventListener("error", (event) => {
        // Named "error" by the server's event contract, not the transport's.
        const raw = (event as MessageEvent).data;
        if (raw) {
          setStatus((current) => ({
            ...current,
            state: "failed",
            error: JSON.parse(raw) as ApiError,
          }));
          return;
        }
        // A transport error. While the browser is reconnecting, wait. Once it
        // has given up (a restarted service, or a 404 for an operation the
        // service no longer knows), the stream will never say "finished", so
        // ask for the operation's own state instead of staying "running".
        if (source.readyState !== EventSource.CLOSED || sourceRef.current !== source) return;
        close();
        void api.operation(snapshot.id).then(
          (latest) => {
            setStatus((current) => ({ ...current, state: latest.state === "running" ? "failed" : latest.state,
              error: latest.state === "running" ? LOST_STREAM : current.error }));
            if (latest.state !== "running") finishedRef.current?.(latest.state);
          },
          () => setStatus((current) => ({ ...current, state: "failed", error: LOST_STREAM })),
        );
      });
      source.addEventListener("finished", (event) => {
        const data = JSON.parse((event as MessageEvent).data) as { state: OperationState };
        setStatus((current) => ({ ...current, state: data.state }));
        close();
        finishedRef.current?.(data.state);
      });
      return snapshot.id;
    },
    [close],
  );

  const cancel = useCallback(async () => {
    if (!status.id) return;
    await api.cancelOperation(status.id).catch(() => undefined);
  }, [status.id]);

  const reset = useCallback(() => {
    close();
    setStatus(IDLE);
  }, [close]);

  return { status, start, cancel, reset };
}
