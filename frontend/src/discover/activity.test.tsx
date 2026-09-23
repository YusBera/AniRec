import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useRecommendationActivity } from "./useRecommendationActivity";
import { api } from "../api/client";
import type { Feed, RecommendationViewModel } from "../api/types";

const model = { mal_id: 1, rank: 2 } as RecommendationViewModel;
const feed = { ephemeral: false, state_profile_id: "profile", activity_feed_id: "a".repeat(64), recommendations: [model] } as Feed;

let hook: ReturnType<typeof useRecommendationActivity>;
function Surface({ covered = false, sample = false, hide = false }) {
  hook = useRecommendationActivity(sample ? { ...feed, ephemeral: true } : feed, covered);
  return hide ? null : <article data-activity-mal-id="1">One</article>;
}

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("records a saved action with its original position after the card disappears", async () => {
  vi.spyOn(api, "activityStatus").mockResolvedValue({ enabled: true, local_only: true, retention_days: 90 });
  const events = vi.spyOn(api, "activityEvent").mockResolvedValue({ recorded: true });
  const { rerender } = render(<Surface />);
  await waitFor(() => expect(hook.enabled).toBe(true));
  const commit = hook.prepare(model, "dismiss");
  rerender(<Surface hide />);
  expect(events).not.toHaveBeenCalled();
  commit?.();
  await waitFor(() => expect(events).toHaveBeenCalledOnce());
  expect(events.mock.calls[0]?.[0]).toMatchObject({ position: 1, model_rank: 2, action: "dismiss" });
});

it("requires visible dwell, deduplicates impressions, and excludes covered cards", async () => {
  vi.spyOn(api, "activityStatus").mockResolvedValue({ enabled: true, local_only: true, retention_days: 90 });
  const events = vi.spyOn(api, "activityEvent").mockResolvedValue({ recorded: true });
  vi.useFakeTimers();
  const { rerender } = render(<Surface covered />);
  await act(async () => { await Promise.resolve(); });
  expect(hook.enabled).toBe(true);
  const node = screen.getByText("One");
  vi.spyOn(node, "getBoundingClientRect").mockReturnValue({ left: 0, top: 0, right: 100, bottom: 100, width: 100, height: 100 } as DOMRect);
  vi.spyOn(document, "hasFocus").mockReturnValue(true);
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  Object.defineProperty(document, "elementFromPoint", { configurable: true, value: () => node });
  await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
  expect(events).not.toHaveBeenCalled();
  rerender(<Surface />);
  await act(async () => { await vi.advanceTimersByTimeAsync(750); });
  expect(events).not.toHaveBeenCalled();
  await act(async () => { await vi.advanceTimersByTimeAsync(750); });
  expect(events).toHaveBeenCalledOnce();
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(events).toHaveBeenCalledOnce();
});

it("never persists sample activity", async () => {
  const status = vi.spyOn(api, "activityStatus");
  const events = vi.spyOn(api, "activityEvent");
  render(<Surface sample />);
  hook.record(model, "detail_open");
  expect(status).not.toHaveBeenCalled();
  expect(events).not.toHaveBeenCalled();
});


it("drains pending events before clearing and invalidates previously prepared actions", async () => {
  vi.spyOn(api, "activityStatus").mockResolvedValue({ enabled: true, local_only: true, retention_days: 90 });
  let finish!: (value: { recorded: boolean }) => void;
  const events = vi.spyOn(api, "activityEvent").mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  const clear = vi.spyOn(api, "clearActivity").mockResolvedValue({ enabled: true });
  render(<Surface />);
  await waitFor(() => expect(hook.enabled).toBe(true));
  const delayed = hook.prepare(model, "dismiss");
  hook.record(model, "detail_open");
  let clearing!: Promise<void>;
  act(() => { clearing = hook.clear(); });
  expect(clear).not.toHaveBeenCalled();
  hook.record(model, "detail_open");
  expect(events).toHaveBeenCalledOnce();
  await act(async () => { finish({ recorded: true }); await clearing; });
  expect(clear).toHaveBeenCalledOnce();
  delayed?.();
  expect(events).toHaveBeenCalledOnce();
});

it("includes the originating profile and drops prepared actions after a profile change", async () => {
  vi.spyOn(api, "activityStatus").mockResolvedValue({ enabled: true, local_only: true, retention_days: 90 });
  const events = vi.spyOn(api, "activityEvent").mockResolvedValue({ recorded: true });
  const { rerender } = render(<Surface />);
  await waitFor(() => expect(hook.enabled).toBe(true));
  hook.record(model, "detail_open");
  expect(events.mock.calls[0]?.[0]).toMatchObject({ profile_id: "profile" });
  const delayed = hook.prepare(model, "dismiss");
  rerender(<Surface sample />);
  delayed?.();
  expect(events).toHaveBeenCalledOnce();
});
