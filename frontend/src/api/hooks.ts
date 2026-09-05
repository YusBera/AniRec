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

export function useFeed() {
  const [feed, setFeed] = useState<Feed | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(async (options?: { quiet?: boolean }) => {
    if (!options?.quiet) setState("loading");
    try {
      const next = await api.feed();
      setFeed(next);
      setError(null);
      setState("ready");
    } catch (caught) {
      if (caught instanceof AniRecApiError) setError(caught.detail);
      setState("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { feed, state, error, reload: load, setFeed };
}

export interface OperationProgress {
  id: string | null;
  state: OperationState | "idle";
  progress: ProgressEvent | null;
  error: ApiError | null;
}

const IDLE: OperationProgress = { id: null, state: "idle", progress: null, error: null };

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
      setStatus({ ...IDLE, state: "running" });
      let snapshot;
      try {
        snapshot = await api.startOperation(kind, payload);
      } catch (caught) {
        const detail =
          caught instanceof AniRecApiError
            ? caught.detail
            : { ...IDLE.error! };
        setStatus({ id: null, state: "failed", progress: null, error: detail });
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
        if (!raw) return;
        setStatus((current) => ({
          ...current,
          state: "failed",
          error: JSON.parse(raw) as ApiError,
        }));
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
