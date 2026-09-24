/**
 * The rail's SYSTEM readout and ACTIVITY console, from `gui/main_window.py`
 * (`SystemReadout`, `_refresh_system_readout`) and `gui/system_log.py`.
 *
 * The desktop's rule for both panels is the rule here: every row and every
 * line corresponds to something the application actually knows. ENGINE comes
 * from `active_operations`, PROFILE and MAL from `/api/system/state`, SOURCE
 * from the feed's `source`, and the console from `/api/operations` and the
 * operations' own event streams. Nothing is written to fill the panel out.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Feed, OperationSnapshot, ProgressEvent, SystemState } from "../api/types";

export interface LogLine {
  id: number;
  /** When this client saw the event; null for history already present at load. */
  time: string | null;
  tag: "BOOT" | "ENGINE" | "ERROR" | "SOURCE";
  message: string;
}

/** Lines retained, as `system_log.MAX_LINES`. Older lines are dropped. */
export const MAX_LINES = 200;
const BUSY_POLL_MS = 3000;
const IDLE_POLL_MS = 20000;

const clock = () => new Date().toLocaleTimeString("en-GB", { hour12: false });

/** `render_meter`: a bounded text meter, e.g. "[||||||    ]  60%". */
export function renderMeter(current: number, total: number, cells = 10): string {
  const value = total > 0 && Number.isFinite(current) ? Math.max(0, Math.min(100, (current / total) * 100)) : 0;
  const filled = Math.max(0, Math.min(cells, Math.round((cells * value) / 100)));
  return `[${"|".repeat(filled)}${" ".repeat(cells - filled)}] ${Math.round(value).toString().padStart(3)}%`;
}

export function useShellState() {
  const [system, setSystem] = useState<SystemState | null>(null);
  const [systemFailed, setSystemFailed] = useState(false);
  const [version, setVersion] = useState<string | null>(null);
  const [lines, setLines] = useState<LogLine[]>([]);
  const nextId = useRef(0);
  const seen = useRef<Map<string, OperationSnapshot["state"]> | null>(null);
  const streams = useRef(new Map<string, EventSource>());
  const busy = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const kick = useRef<() => void>(() => undefined);

  const log = useCallback((tag: LogLine["tag"], message: string, stamped = true) => {
    setLines((current) => [...current, { id: nextId.current++, time: stamped ? clock() : null, tag, message }].slice(-MAX_LINES));
  }, []);

  const follow = useCallback((operation: OperationSnapshot) => {
    if (streams.current.has(operation.id) || typeof EventSource === "undefined") return;
    const source = new EventSource(api.eventsUrl(operation.id));
    streams.current.set(operation.id, source);
    let last = "";
    source.addEventListener("progress", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as ProgressEvent;
      // A stage change earns a line; a counter tick does not.
      if (data.message && data.message !== last) {
        last = data.message;
        log("ENGINE", data.total > 0 ? `${data.message} ${renderMeter(data.current, data.total)}` : data.message);
      }
    });
    source.addEventListener("error", (event) => {
      const raw = (event as MessageEvent).data;
      if (!raw) return;
      try { log("ERROR", `${operation.kind}: ${(JSON.parse(raw) as { title?: string }).title ?? "failed"}`); } catch { /* not the server's frame */ }
    });
    source.addEventListener("finished", () => {
      source.close();
      streams.current.delete(operation.id);
      void refreshRef.current();
    });
  }, [log]);

  const inflight = useRef<Promise<void> | null>(null);
  const refresh = useCallback(() => {
    // Overlapping polls would each read "first" and log history twice.
    inflight.current ??= poll().finally(() => { inflight.current = null; });
    return inflight.current;
  }, []);
  const poll = async () => {
    const [state, operations] = await Promise.allSettled([api.systemState(), api.operations()]);
    if (state.status === "fulfilled") { setSystem(state.value); setSystemFailed(false); } else setSystemFailed(true);
    if (operations.status !== "fulfilled") return;
    const records = operations.value.operations ?? [];
    const first = seen.current === null;
    const known = seen.current ?? new Map();
    for (const record of records) {
      const before = known.get(record.id);
      if (first) {
        // History already there when the page loaded: no time is invented for it.
        log("ENGINE", `${record.kind} · ${record.state}`, false);
      } else if (before === undefined) {
        log("ENGINE", record.state === "running" ? `${record.kind} started` : `${record.kind} · ${record.state}`);
      } else if (before !== record.state) {
        log(record.state === "failed" ? "ERROR" : "ENGINE", `${record.kind} ${record.state}`);
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
    api.health().then((health) => {
      if (cancelled) return;
      setVersion(health.version);
      log("BOOT", `core ${health.version} online`);
    }).catch(() => { if (!cancelled) log("ERROR", "local service unreachable"); });
    const loop = async () => {
      if (timer.current) clearTimeout(timer.current);
      await refreshRef.current().catch(() => undefined);
      if (!cancelled) timer.current = setTimeout(loop, busy.current ? BUSY_POLL_MS : IDLE_POLL_MS);
    };
    kick.current = () => void loop();
    void loop();
    const open = streams.current;
    return () => {
      cancelled = true;
      kick.current = () => undefined;
      if (timer.current) clearTimeout(timer.current);
      open.forEach((source) => source.close());
      open.clear();
    };
  }, [log]);

  /** Called when this client starts an operation, so ENGINE turns BUSY at once. */
  const nudge = useCallback(() => kick.current(), []);

  return { system, systemFailed, version, lines, log, nudge };
}

type Tone = "ok" | "warn" | "busy" | "idle" | "error";

export function readoutRows(system: SystemState | null, systemFailed: boolean, feed: Feed | null): [string, string, Tone, string][] {
  const unknown = !system;
  const engine: [string, Tone] = unknown ? [systemFailed ? "OFFLINE" : "--", systemFailed ? "error" : "idle"]
    : system.active_operations?.length ? ["BUSY", "busy"] : ["READY", "ok"];
  const source: [string, Tone] = !feed ? ["--", "idle"] : feed.source === "sample" ? ["SAMPLE", "warn"] : feed.source === "profile" ? ["LIVE", "ok"] : ["NONE", "idle"];
  const profile = system?.profile?.username;
  const mal: [string, Tone] = unknown ? ["--", "idle"] : system.mal_client_id_present ? ["CLIENT ID", "ok"] : ["NO CLIENT ID", "warn"];
  return [
    ["ENGINE", engine[0], engine[1], unknown ? "Engine state unknown" : `Engine ${engine[0].toLocaleLowerCase()}`],
    ["SOURCE", source[0], source[1], feed ? `Source ${source[0].toLocaleLowerCase()}` : "Source unknown"],
    ["PROFILE", unknown ? "--" : profile ?? "NONE", profile ? "ok" : "idle", unknown ? "Profile unknown" : profile ? `Profile ${profile}` : "No active profile"],
    ["MAL", mal[0], mal[1], unknown ? "MyAnimeList state unknown" : system.mal_client_id_present ? "MyAnimeList Client ID configured" : "No MyAnimeList Client ID configured"],
  ];
}

export function SystemReadout({ rows }: { rows: ReturnType<typeof readoutRows> }) {
  return <section className="system-readout" aria-labelledby="system-caption">
    <h2 className="rail-caption" id="system-caption">SYSTEM</h2>
    <dl>{rows.map(([key, value, tone, spoken]) => <div key={key} className="readout-row">
      <dt><span className="lamp" data-tone={tone} aria-hidden="true" />{key}</dt>
      <dd data-tone={tone}><span aria-hidden="true">{value}</span><span className="visually-hidden">{spoken}</span></dd>
    </div>)}</dl>
  </section>;
}

export function ActivityConsole({ lines }: { lines: LogLine[] }) {
  const [expanded, setExpanded] = useState(false);
  const body = useRef<HTMLOListElement>(null);
  const pinned = useRef(true);
  useEffect(() => {
    // Follow the tail unless the reader has scrolled away from it.
    const node = body.current;
    if (node && pinned.current) node.scrollTop = node.scrollHeight;
  }, [lines]);
  return <section className="activity-console" aria-labelledby="activity-caption" data-expanded={expanded}>
    <div className="console-head">
      <h2 className="rail-caption" id="activity-caption">ACTIVITY</h2>
      <button type="button" className="console-toggle" aria-expanded={expanded} aria-label={expanded ? "Shrink the activity console" : "Expand the activity console"}
        onClick={() => setExpanded((open) => !open)}>{expanded ? "−" : "+"}</button>
    </div>
    <ol ref={body} className="console-lines" role="log" aria-label="Activity" tabIndex={0}
      onScroll={(event) => { const node = event.currentTarget; pinned.current = node.scrollHeight - node.scrollTop - node.clientHeight < 8; }}>
      {lines.length ? lines.map((line) => <li key={line.id} data-tag={line.tag}>
        <span className="console-stamp">{line.time ?? "--:--:--"}</span> <span className="console-tag">{line.tag}</span>
        <span className="console-message">{line.message}</span>
      </li>) : <li className="console-empty">No activity recorded yet.</li>}
    </ol>
  </section>;
}
