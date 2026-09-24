/**
 * What the shell knows about the service, told as notifications (D-019).
 *
 * The rail's SYSTEM readout and ACTIVITY console are gone: a newcomer should
 * not have to read machine state to use the site. The same real events now
 * reach the bell in the top bar, in plain words, and only the ones a person
 * cares about: a refresh or sync finished, failed or was stopped, or the
 * local service stopped answering. Nothing is invented: every notification
 * comes from `/api/operations`, an operation's own event stream, or a failed
 * `/api/system/state` poll. History already present when the page loads is
 * not announced.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { OperationSnapshot, SystemState } from "../api/types";

export interface Notice {
  id: number;
  /** When this page saw the event. */
  at: Date;
  tone: "info" | "done" | "problem";
  title: string;
  detail?: string;
}

/** Notifications kept; older ones are dropped. */
export const MAX_NOTICES = 50;
const BUSY_POLL_MS = 3000;
const IDLE_POLL_MS = 20000;

/** The operations a reader would recognise, in the words they would use. */
const OPERATION_WORDS: Record<string, { done: string; doneDetail?: string; name: string }> = {
  refresh: { done: "Checked your MyAnimeList list", doneDetail: "Your recommendations are up to date.", name: "Checking your list" },
  recommendation: { done: "Your recommendations were rebuilt", name: "Rebuilding your recommendations" },
  "more-recommendations": { done: "More recommendations are ready", name: "Loading more recommendations" },
  sync: { done: "Your MyAnimeList list was synced", name: "Syncing your list" },
  "list-sync": { done: "Checked your Watch Later list", doneDetail: "Anything you finished on MyAnimeList has been noted.", name: "Checking your Watch Later list" },
};

/** The notification an operation's state change earns, or null for none. */
export function operationNotice(kind: string, state: OperationSnapshot["state"], errorTitle?: string): Omit<Notice, "id" | "at"> | null {
  const words = OPERATION_WORDS[kind];
  if (!words) return null;
  if (state === "succeeded") return { tone: "done", title: words.done, detail: words.doneDetail };
  if (state === "failed") return { tone: "problem", title: `${words.name} didn't finish`, detail: errorTitle || undefined };
  if (state === "cancelled") return { tone: "info", title: `${words.name} was stopped` };
  return null;
}

export function useShellState() {
  const [system, setSystem] = useState<SystemState | null>(null);
  const [systemFailed, setSystemFailed] = useState(false);
  const [version, setVersion] = useState<string | null>(null);
  const [notices, setNotices] = useState<Notice[]>([]);
  const nextId = useRef(0);
  const seen = useRef<Map<string, OperationSnapshot["state"]> | null>(null);
  const errors = useRef(new Map<string, string>());
  const streams = useRef(new Map<string, EventSource>());
  const busy = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const kick = useRef<() => void>(() => undefined);
  const failedBefore = useRef(false);

  const notify = useCallback((notice: Omit<Notice, "id" | "at">) => {
    setNotices((current) => [...current, { ...notice, id: nextId.current++, at: new Date() }].slice(-MAX_NOTICES));
  }, []);

  const follow = useCallback((operation: OperationSnapshot) => {
    if (streams.current.has(operation.id) || typeof EventSource === "undefined") return;
    const source = new EventSource(api.eventsUrl(operation.id));
    streams.current.set(operation.id, source);
    source.addEventListener("error", (event) => {
      const raw = (event as MessageEvent).data;
      if (!raw) return;
      // Kept for the "didn't finish" notification the next poll produces.
      try { errors.current.set(operation.id, (JSON.parse(raw) as { title?: string }).title ?? ""); } catch { /* not the server's frame */ }
    });
    source.addEventListener("finished", () => {
      source.close();
      streams.current.delete(operation.id);
      void refreshRef.current();
    });
  }, []);

  const inflight = useRef<Promise<void> | null>(null);
  const refresh = useCallback(() => {
    // Overlapping polls would each read "first" and treat history as new.
    inflight.current ??= poll().finally(() => { inflight.current = null; });
    return inflight.current;
  }, []);
  const poll = async () => {
    const [state, operations] = await Promise.allSettled([api.systemState(), api.operations()]);
    if (state.status === "fulfilled") {
      setSystem(state.value);
      setSystemFailed(false);
      if (failedBefore.current) notify({ tone: "done", title: "AniRec is connected again" });
      failedBefore.current = false;
    } else {
      setSystemFailed(true);
      // One notification per outage, not one per poll.
      if (!failedBefore.current) notify({ tone: "problem", title: "AniRec can't reach its local service", detail: "What you see may be out of date until it is back." });
      failedBefore.current = true;
    }
    if (operations.status !== "fulfilled") return;
    const records = operations.value.operations ?? [];
    const first = seen.current === null;
    const known = seen.current ?? new Map();
    for (const record of records) {
      const before = known.get(record.id);
      // Only a change seen while the page is open is news.
      if (!first && before !== record.state && record.state !== "running") {
        const notice = operationNotice(record.kind, record.state, errors.current.get(record.id));
        if (notice) notify(notice);
      }
      known.set(record.id, record.state);
      if (record.state === "running") follow(record);
    }
    seen.current = known;
    busy.current = records.some((record) => record.state === "running");
  };
  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;

  useEffect(() => {
    let cancelled = false;
    api.health().then((health) => { if (!cancelled) setVersion(health.version); }).catch(() => undefined);
    // One polling chain at a time. Each run takes a generation number; a run
    // superseded by a nudge while its poll was in flight schedules nothing.
    let generation = 0;
    const loop = async (fresh = false) => {
      const mine = ++generation;
      if (timer.current) clearTimeout(timer.current);
      // A nudge must read the state after the start, not a poll already in flight.
      if (fresh) await inflight.current?.catch(() => undefined);
      await refreshRef.current().catch(() => undefined);
      if (cancelled || mine !== generation) return;
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => void loop(), busy.current ? BUSY_POLL_MS : IDLE_POLL_MS);
    };
    kick.current = () => void loop(true);
    void loop();
    const open = streams.current;
    return () => {
      cancelled = true;
      kick.current = () => undefined;
      if (timer.current) clearTimeout(timer.current);
      open.forEach((source) => source.close());
      open.clear();
    };
  }, []);

  /** Called when this client starts an operation, so its outcome is seen promptly. */
  const nudge = useCallback(() => kick.current(), []);

  return { system, systemFailed, version, notices, notify, nudge };
}
