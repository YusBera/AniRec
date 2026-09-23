import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Feed, RecommendationViewModel } from "../api/types";

type Action = Parameters<typeof api.activityEvent>[0]["action"];

/** Local-only opt-in activity; rendered cards must actually stay in view. */
export function useRecommendationActivity(feed: Feed | null | undefined, covered: boolean) {
  const [enabled, setEnabledState] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const paused = useRef(false);
  const requests = useRef(new Set<Promise<unknown>>());
  const state = useRef({ request: crypto.randomUUID(), seen: new Set<number>(), since: new Map<number, number>(), inflight: new Set<number>() });
  const current = useRef({ feed, covered, enabled });
  current.current = { feed, covered, enabled };
  const profile = feed?.ephemeral ? null : feed?.state_profile_id;
  const fingerprint = feed?.activity_feed_id;

  useEffect(() => {
    state.current = { request: crypto.randomUUID(), seen: new Set(), since: new Map(), inflight: new Set() };
  }, [profile, fingerprint, enabled]);

  useEffect(() => {
    let cancelled = false;
    setEnabledState(false);
    setLoaded(false);
    setNotice("");
    if (!profile || typeof api.activityStatus !== "function") return;
    void api.activityStatus().then((result) => {
      if (!cancelled) { setEnabledState(result.enabled === true); setLoaded(true); }
    }).catch(() => { if (!cancelled) setNotice("Activity settings could not be loaded. Nothing is being recorded."); });
    return () => { cancelled = true; };
  }, [profile]);

  const prepare = useCallback((model: RecommendationViewModel, action: Action) => {
    const { feed: live, enabled: on } = current.current;
    if (paused.current || !on || !live || live.ephemeral || !live.state_profile_id || !live.activity_feed_id || !model.mal_id) return;
    const cards = Array.from(document.querySelectorAll<HTMLElement>("[data-activity-mal-id]"));
    const index = cards.findIndex((node) => Number(node.dataset.activityMalId) === model.mal_id);
    if (index < 0) return;
    const session = state.current;
    if (action === "impression" && (session.seen.has(model.mal_id) || session.inflight.has(model.mal_id))) return;
    if (action === "impression") session.inflight.add(model.mal_id);
    const payload = {
      profile_id: live.state_profile_id, event_id: crypto.randomUUID(), request_id: session.request, feed_id: live.activity_feed_id,
      action, mal_id: model.mal_id, position: index + 1, model_rank: model.rank, surface: "web_cards" as const,
    };
    return () => {
      if (paused.current || session !== state.current || current.current.feed?.state_profile_id !== live.state_profile_id || !current.current.enabled) return;
      const request = api.activityEvent(payload).then(() => {
        // A duplicate receipt also finishes the exposure attempt.
        if (action === "impression") session.seen.add(model.mal_id!);
      }).catch(() => {
        // Best effort: avoid retrying a failed local endpoint every 250ms.
        if (action === "impression") session.seen.add(model.mal_id!);
      }).finally(() => { session.inflight.delete(model.mal_id!); requests.current.delete(request); });
      requests.current.add(request);
    };
  }, []);
  const record = useCallback((model: RecommendationViewModel, action: Action) => prepare(model, action)?.(), [prepare]);

  useEffect(() => {
    if (!enabled || !profile) return;
    const sample = () => {
      const session = state.current;
      const live = current.current;
      if (paused.current || !live.enabled || live.covered || document.visibilityState !== "visible" || !document.hasFocus()) {
        session.since.clear();
        return;
      }
      const visible = new Set<number>();
      for (const node of document.querySelectorAll<HTMLElement>("[data-activity-mal-id]")) {
        const rect = node.getBoundingClientRect();
        const width = Math.max(0, Math.min(rect.right, innerWidth) - Math.max(rect.left, 0));
        const height = Math.max(0, Math.min(rect.bottom, innerHeight) - Math.max(rect.top, 0));
        const id = Number(node.dataset.activityMalId);
        if (!id || rect.width * rect.height <= 0 || width * height < .5 * rect.width * rect.height) continue;
        const hit = document.elementFromPoint(
          (Math.max(rect.left, 0) + Math.min(rect.right, innerWidth)) / 2,
          (Math.max(rect.top, 0) + Math.min(rect.bottom, innerHeight)) / 2,
        );
        if (!hit || !node.contains(hit)) continue;
        visible.add(id);
        if (!session.since.has(id)) session.since.set(id, performance.now());
        if (performance.now() - session.since.get(id)! >= 1000) {
          const model = live.feed?.recommendations.find((m) => m.mal_id === id);
          if (model) record(model, "impression");
        }
      }
      for (const id of session.since.keys()) if (!visible.has(id)) session.since.delete(id);
    };
    const timer = window.setInterval(sample, 250);
    const reset = () => state.current.since.clear();
    window.addEventListener("blur", reset);
    document.addEventListener("visibilitychange", reset);
    return () => {
      clearInterval(timer);
      window.removeEventListener("blur", reset);
      document.removeEventListener("visibilitychange", reset);
    };
  }, [enabled, profile, record]);

  const setEnabled = async (value: boolean) => {
    paused.current = true;
    setPending(true);
    try {
      await Promise.allSettled(requests.current);
      if (current.current.feed?.state_profile_id !== profile) return;
      const result = await api.activitySetting(value);
      if (current.current.feed?.state_profile_id !== profile) return;
      setEnabledState(result.enabled === true);
      setNotice(result.enabled ? "Activity is saved on this device only." : "Activity recording is off.");
    } catch { setNotice("Could not save the activity setting. Try again."); }
    finally { paused.current = false; setPending(false); }
  };
  const clear = async () => {
    paused.current = true;
    setPending(true);
    try {
      await Promise.allSettled(requests.current);
      if (current.current.feed?.state_profile_id !== profile) return;
      await api.clearActivity();
      state.current = { request: crypto.randomUUID(), seen: new Set(), since: new Map(), inflight: new Set() };
      setNotice("Saved recommendation activity cleared.");
    } catch { setNotice("Could not clear saved activity. Try again."); }
    finally { paused.current = false; setPending(false); }
  };
  return { enabled, loaded, pending, notice, setEnabled, clear, record, prepare };
}
