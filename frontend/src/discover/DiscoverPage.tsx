/**
 * Discover and My Library, against the real API.
 *
 * Qt equivalents: `discover_page.py` (the instrument header), the explorer in
 * `recommendation_page.py` (control bar, views, empty states, collections)
 * and the parts of `main_window.py` that own the feed's operations.
 *
 * Decisions are optimistic with a rollback, which the desktop does not need
 * to think about because a service call there is in-process. Over HTTP a
 * decision is a round trip, and waiting for it before repainting makes a
 * button feel broken. Writes are serialized: every response carries the whole
 * local state, so a late response must not erase a newer decision.
 *
 * When the feed is ephemeral - the bundled sample library, which has no
 * profile directory to write to - decisions are held in local state only.
 * That is exactly what _enter_demo_mode does with set_ephemeral(True).
 *
 * Like and Dislike are gone (D-015): a card is judged before the anime is
 * watched, so the only decisions it offers are Watch Later and Not interested.
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { AniRecApiError, api } from "../api/client";
import { OPERATION_RUNNING, useFeed, useOperation } from "../api/hooks";
import type { Feed, LocalState, RecommendationViewModel } from "../api/types";
import { Icon } from "../assets/Icon";
import { Controls } from "./Controls";
import { DiscoverHeader } from "./DiscoverHeader";
import { FeedView, ViewToggle } from "./FeedViews";
import type { Decision } from "./RecommendationCard";
import { ScoreInspector } from "./ScoreInspector";
import { rankingEngineId } from "./ScoreRail";
import { EMPTY_FILTERS, activeFilterCount, filterAndSort, isActive } from "./filtering";
import { EmptyPanel, ErrorPanel, FeedSkeleton } from "./states";
import "./discover.css";
import { LibraryPage } from "../workspace/LibraryPage";
import { PAGE_SIZE, PageControls } from "../workspace/common";
import { useRecommendationActivity } from "./useRecommendationActivity";
import { readDiscoverLocation, useDiscoverLocation } from "./discoverUrl";

export const NO_PROFILE_REASON = "Recommendation lists need a profile.";
// Connecting an account from the web client is not possible (user decision,
// 2026-09-24), so no copy here offers or promises one.
export const RUN_UNAVAILABLE = "Not available for the sample library.";
/** Errors whose advice is to connect the account again, which the web
 *  client cannot do (D-017). */
const ACCOUNT_ERRORS = new Set(["auth_error", "auth_timeout"]);
export const REFRESH_TITLE = "Check your MyAnimeList list and rebuild the feed if anything changed.";

/** The profile a refresh already ran for in this browser session. */
const REFRESHED_KEY = "anirec.feedRefreshed";
function refreshedProfiles(): string[] {
  try {
    const stored: unknown = JSON.parse(sessionStorage.getItem(REFRESHED_KEY) ?? "[]");
    return Array.isArray(stored) ? stored.filter((id): id is string => typeof id === "string") : [];
  } catch { return []; }
}
function refreshedThisSession(profileId: string): boolean {
  return refreshedProfiles().includes(profileId);
}
function rememberRefreshed(profileId: string) {
  try { sessionStorage.setItem(REFRESHED_KEY, JSON.stringify([...refreshedProfiles(), profileId])); } catch { /* private mode: refresh again next load */ }
}

interface Inspecting {
  malId: number | null;
  title: string;
  list: RecommendationViewModel[];
}

/** The one fact the control bar states, in plain words (D-019). Saved and
 *  Not interested counts live on the My Library tabs, where they are used. */
export function feedCount(count: number): string {
  return count === 1 ? "1 recommendation" : `${count.toLocaleString("en-US")} recommendations`;
}

export function DiscoverPage({ surface = "discover", onFeedChange, onOperationStarted, autoRefresh = false, activeProfileId = null, initialImporting = false }: {
  surface?: "discover" | "library" | "inactive";
  /** The service's active profile. A profile with no feed yet is served the
   *  sample library, so this, not the feed, says whether a refresh can run. */
  activeProfileId?: string | null;
  /** The username import is reading a list before its profile is available. */
  initialImporting?: boolean;
  /** Refresh the profile's feed once per session when it is opened (D-018).
   *  The workspace turns this on; a bare page in a test does not. */
  autoRefresh?: boolean;
  /** Lets the shell report SOURCE and the sample banner from the same feed. */
  onFeedChange?: (feed: Feed | null) => void;
  /** Lets the shell refresh ENGINE and ACTIVITY as soon as a run starts. */
  onOperationStarted?: () => void;
}) {
  const [locationState, updateLocation] = useDiscoverLocation();
  const { filters, page, view, showHidden } = locationState;
  const sortMode = locationState.sort;
  // A profile feed asks the service for its Not interested titles. The sample
  // feed must not be refetched: its decisions live only in this page, and a
  // reload would silently discard them.
  const [fetchHidden, setFetchHidden] = useState(() => readDiscoverLocation().showHidden);
  const queryKey = JSON.stringify({ ...filters, sort: sortMode, page });
  const { feed, state, error, reload, setFeed, loadedQuery } = useFeed(fetchHidden, queryKey);
  useEffect(() => { if (feed && !feed.ephemeral) setFetchHidden(showHidden); }, [feed?.ephemeral, showHidden]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [inspecting, setInspecting] = useState<Inspecting | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [feedbackNotice, setFeedbackNotice] = useState("");
  const [feedbackError, setFeedbackError] = useState<{ message: string; retryable: boolean; vote: [number, Decision, boolean] } | null>(null);
  const controlsId = useId();

  const operation = useOperation((finished) => {
    // A successful run replaces the feed; a cancel or failure leaves what is
    // on screen alone rather than blanking it.
    if (finished === "succeeded") void reload({ quiet: true });
  });

  // A reloaded feed is a new ranking: an inspector still showing the old
  // snapshot would pair its rank and why with the new feed's engine label.
  useEffect(() => setInspecting(null), [feed?.activity_feed_id]);

  // The saved "show not interested" preference sets the checkbox's first
  // state; the server already included those titles in that case.
  const seeded = useRef(false);
  useEffect(() => {
    if (!feed || seeded.current || surface !== "discover") return;
    seeded.current = true;
    if (feed.state.show_hidden && !locationState.hiddenSpecified) updateLocation({ showHidden: true }, true);
  }, [feed, surface]);

  const feedRef = useRef(onFeedChange);
  feedRef.current = onFeedChange;
  useEffect(() => { feedRef.current?.(feed); }, [feed]);

  const localState = feed?.state;
  const feedEngineId = feed ? rankingEngineId(feed.user_stats) : null;
  const activity = useRecommendationActivity(feed, inspecting !== null || surface !== "discover" || view !== "cards");
  const busy = operation.status.state === "running";
  const pending = saving || busy;
  const decisionsUnavailable = feed && !feed.ephemeral && !feed.state_profile_id ? NO_PROFILE_REASON : undefined;
  // Refreshing needs a profile, even if the current feed is sample data.
  const profileId = feed && !feed.ephemeral ? feed.state_profile_id : activeProfileId;
  const refreshUnavailable = profileId ? null : RUN_UNAVAILABLE;
  const hideSampleFeed = !!profileId && !!feed?.ephemeral;
  const firstFeedLoading = initialImporting || (!!profileId
    && (hideSampleFeed || feed?.recommendations.length === 0)
    && (busy || (hideSampleFeed && state !== "error" && operation.status.state === "succeeded")));

  const inspect = (model: RecommendationViewModel, list: RecommendationViewModel[]) => {
    if (surface === "discover") activity.record(model, "detail_open");
    setInspecting({ malId: model.mal_id, title: model.display_title, list });
  };

  const vote = useCallback(
    async (malId: number, action: Decision, value: boolean, known?: RecommendationViewModel) => {
      if (!feed || savingRef.current || operation.status.state === "running") return;
      setFeedbackError(null);
      const model = known ?? feed.recommendations.find((m) => m.mal_id === malId)
        ?? inspecting?.list.find((m) => m.mal_id === malId);
      const title = model?.display_title ?? "Title";
      const outcome = action === "watch_later"
        ? (value ? "saved for later" : "removed from Watch Later")
        : (value ? "marked Not interested" : "brought back to For You");
      const finishActivity = model && surface === "discover"
        ? activity.prepare(model, action === "watch_later" ? (value ? "watch_later_add" : "watch_later_remove") : (value ? "dismiss" : "restore"))
        : undefined;
      const previous = feed.state;
      setFeed({ ...feed, state: applyVote(previous, malId, action, value) });

      if (feed.ephemeral || !feed.state_profile_id) {
        setFeedbackNotice(`${title} ${outcome} in this preview. Changes reset on reload.`);
        return;
      }

      savingRef.current = true;
      setSaving(true);
      setFeedbackNotice(`Saving decision for ${title}…`);
      try {
        const response = await api.feedback({ profile_id: feed.state_profile_id, mal_id: malId, action, value });
        setFeed((current) => (current ? { ...current, state: response.state } : current));
        setFeedbackNotice(`${title} ${outcome}.`);
        finishActivity?.();
        if (action === "hidden" && feed.page_size === PAGE_SIZE) await reload({ quiet: true });
      } catch (caught) {
        // Roll back rather than leaving the card showing a decision the
        // profile does not have.
        setFeed((current) => (current ? { ...current, state: previous } : current));
        const detail = caught instanceof AniRecApiError ? caught.detail : null;
        setFeedbackNotice("");
        setFeedbackError({
          message: `Decision for ${title} was not saved. ${detail ? [detail.title, detail.solution].filter(Boolean).join(". ") : "The service returned an unexpected response."} The previous state is restored.`,
          retryable: detail?.retryable ?? false,
          vote: [malId, action, value],
        });
      } finally {
        savingRef.current = false;
        setSaving(false);
      }
    },
    [feed, setFeed, operation.status.state, activity.prepare, surface, inspecting, reload],
  );

  const isHidden = useCallback((malId: number | null) => has(localState?.hidden_mal_ids, malId), [localState]);
  const isSaved = useCallback((malId: number | null) => has(localState?.watch_later_mal_ids, malId), [localState]);

  // The For You feed leaves out Not interested titles unless asked, as the
  // desktop's "all" collection does. A title marked in this session drops
  // out at once; "Show not interested" asks the service for all of them.
  const visible = useMemo(
    () => (feed ? filterAndSort(feed.recommendations.filter((m) => showHidden || !has(feed.state.hidden_mal_ids, m.mal_id)), filters, sortMode) : []),
    [feed, filters, sortMode, showHidden],
  );
  const serverPaged = feed?.page_size === PAGE_SIZE && !feed.ephemeral;
  const visibleCount = serverPaged ? (feed.total ?? 0) : visible.length;
  const currentPage = serverPaged ? (loadedQuery === queryKey ? (feed.page ?? page) : page)
    : Math.min(page, Math.max(0, Math.ceil(visibleCount / PAGE_SIZE) - 1));
  useEffect(() => {
    if (feed && state === "ready" && page !== currentPage) updateLocation({ page: currentPage }, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feed, page, currentPage, state]);
  const pageItems = serverPaged ? feed.recommendations.filter((m) => showHidden || !has(feed.state.hidden_mal_ids, m.mal_id))
    : visible.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  const pageMetadataIds = pageItems.map((item) => item.mal_id).filter((id): id is number => id !== null).join(",");
  const requestedMetadata = useRef(new Set<string>());
  useEffect(() => {
    if (surface !== "discover" || !feed || feed.ephemeral || !pageMetadataIds) return;
    const feedId = feed.activity_feed_id;
    const key = `${feedId}:${pageMetadataIds}`;
    if (requestedMetadata.current.has(key)) return;
    requestedMetadata.current.add(key);
    void api.pageMetadata(pageMetadataIds.split(",").map(Number)).then((models) => {
      if (!models.length) return;
      const updates = new Map(models.map((model) => [model.mal_id, model]));
      setFeed((current) => current?.activity_feed_id === feedId
        ? { ...current, recommendations: current.recommendations.map((model) => updates.get(model.mal_id) ?? model) }
        : current);
    }).catch(() => { requestedMetadata.current.delete(key); });
    // Page changes never wait on public metadata; the ranking is already saved.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [surface, feed?.activity_feed_id, feed?.ephemeral, pageMetadataIds, setFeed]);
  const changePage = (next: number) => {
    updateLocation({ page: next });
    document.getElementById("recommendations")?.focus();
  };

  const progress = operation.status.progress;
  const progressNoteId = useId();
  // Pipeline events announce a stage before its work starts. A stage number
  // is not a completed-stage count, and the final stage has no measured ETA.
  const stepTotal = progress?.total ?? 0;
  const stepCurrent = Math.max(0, Math.min(progress?.current ?? 0, stepTotal));
  const finalStep = stepTotal > 0 && stepCurrent === stepTotal;
  const measuredSteps = stepTotal > 0 && !finalStep;
  const completedSteps = Math.max(0, stepCurrent - 1);
  const stepText = stepCurrent > 0 ? `Step ${stepCurrent} of ${stepTotal} · in progress` : "In progress";
  const opError = operation.status.error;
  const start = (kind: string, payload: Record<string, unknown> = {}) => {
    void operation.start(kind, payload).then(() => onOperationStarted?.());
  };
  const refresh = () => start("refresh");

  // Opening a profile checks its MyAnimeList list once per session and
  // rebuilds the feed only if something changed, as the desktop does.
  // Remembered in memory too: when session storage cannot be written, the
  // storage alone forgot every attempt and each finished run started another.
  const autoRefreshed = useRef(new Set<string>());
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!autoRefresh || !profileId || busy || autoRefreshed.current.has(profileId) || refreshedThisSession(profileId)) return;
    autoRefreshed.current.add(profileId);
    rememberRefreshed(profileId);
    autoStarted.current = true;
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, profileId, busy]);

  // An automatic refresh that meets a run another tab started is not a
  // fault: that run is already bringing the feed up to date, and the shell
  // shows it. A refresh the reader asked for still reports the refusal.
  useEffect(() => {
    const state = operation.status.state;
    if (!autoStarted.current || (state !== "failed" && state !== "succeeded" && state !== "cancelled")) return;
    autoStarted.current = false;
    if (state === "failed" && operation.status.error?.code === OPERATION_RUNNING) operation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operation.status.state]);
  const hiddenInFeed = feed ? feed.recommendations.some((m) => has(feed.state.hidden_mal_ids, m.mal_id)) : false;
  // Also exhausted when a reload returns no titles because every one is
  // marked Not interested (the server then reports them only in hidden_count).
  const exhausted = !!feed && !visible.length && !isActive(filters)
    && (feed.recommendations.length > 0 || feed.hidden_count > 0) && !showHidden;

  // The inspector walks the list it was opened from.
  const inspectedIndex = inspecting ? inspecting.list.findIndex((m) => m.mal_id === inspecting.malId && m.display_title === inspecting.title) : -1;
  const inspected = inspecting && inspectedIndex >= 0
    ? feed?.recommendations.find((model) => model.mal_id === inspecting.malId && model.display_title === inspecting.title)
      ?? inspecting.list[inspectedIndex]!
    : null;
  const step = (delta: number) => {
    if (!inspecting || !inspecting.list.length) return;
    const next = inspecting.list[(inspectedIndex + delta + inspecting.list.length) % inspecting.list.length]!;
    if (surface === "discover") activity.record(next, "detail_open");
    setInspecting({ ...inspecting, malId: next.mal_id, title: next.display_title });
  };
  const external = (model: RecommendationViewModel) => { if (surface === "discover") activity.record(model, "external_open"); };

  return (
    <>
      <div hidden={surface !== "discover"}>
      <a className="skip-link" href="#recommendations">Skip to recommendations</a>
      <main className="shell discover">
        {state === "error" && error ? <ErrorPanel error={error} onRetry={() => void reload()} /> : null}

        {feed ? (
          <>
            <div className="discover-workspace-head">
              <DiscoverHeader busy={busy || initialImporting} detail={initialImporting ? "Reading your MyAnimeList list…" : progress?.message}
                count={firstFeedLoading || hideSampleFeed ? undefined : feedCount(visibleCount)} />
              <div className="control-actions">
                {busy ? (
                  <button type="button" className="btn" onClick={() => void operation.cancel()}>Cancel</button>
                ) : (
                  <button type="button" className="btn refresh-feed" disabled={!!refreshUnavailable || saving}
                    title={refreshUnavailable ?? REFRESH_TITLE} onClick={refresh}>
                    <Icon name="refresh" />Refresh</button>
                )}
                {!feed.ephemeral ? <details className="menu">
                  <summary className="btn" title={activity.enabled ? "Saved locally only; retained for up to 90 days and 50,000 events" : "Optional recommendation activity stored on this device only"}>Activity</summary>
                  <div className="menu-body">
                    <label><input type="checkbox" checked={activity.enabled} disabled={activity.pending || !activity.loaded}
                      onChange={(event) => void activity.setEnabled(event.target.checked)} /> Save activity on this device</label>
                    <p>Records visible recommendations and your actions locally. Nothing is uploaded. Keeps up to 90 days and 50,000 events.</p>
                    <button type="button" className="btn" disabled={activity.pending || !activity.loaded}
                      onClick={() => void activity.clear()}>Clear saved activity</button>
                    <p role="status">{activity.notice}</p>
                  </div>
                </details> : null}
                <button type="button" className="btn filter-toggle" aria-expanded={filtersOpen} aria-controls={controlsId}
                  onClick={() => setFiltersOpen((open) => !open)}>
                  <Icon name="filter" />{filtersOpen ? "Hide filters" : "Filters"}
                  {activeFilterCount(filters) ? <span className="filter-count"> · {activeFilterCount(filters)} active</span> : null}
                </button>
                {feed.hidden_count > 0 || hiddenInFeed || showHidden ? <label className="show-hidden">
                  <input type="checkbox" checked={showHidden} disabled={saving} onChange={(event) => {
                    updateLocation({ showHidden: event.target.checked, hiddenSpecified: true, page: 0 });
                    if (!feed.ephemeral) setFetchHidden(event.target.checked);
                  }} /> Show not interested
                </label> : null}
                <ViewToggle view={view} onChange={(next) => updateLocation({ view: next })} />
              </div>
            </div>
            <div className="control-bar" aria-live="off">
              {busy ? (
                <div className="operation-progress">
                <div className="progress-line">
                  <span className="lbl">{progress?.message ?? "Working…"}</span>
                  <div className={`progress-track${measuredSteps ? "" : " indeterminate"}`} role="progressbar"
                    aria-label={progress?.message ?? "Generating recommendations"} aria-valuemin={0}
                    aria-valuemax={measuredSteps ? stepTotal : undefined}
                    aria-valuenow={measuredSteps ? completedSteps : undefined}
                    aria-valuetext={stepText}
                    aria-describedby={finalStep ? progressNoteId : undefined}>
                    <i style={measuredSteps ? { transform: `scaleX(${completedSteps / stepTotal})` } : undefined} />
                  </div>
                  <span className="lbl">{stepText}</span>
                </div>
                {finalStep ? <p id={progressNoteId} className="progress-note" role="status">
                  The final step is still running. Preparing your recommendations can take a while.
                </p> : null}
                </div>
              ) : null}
              {opError ? (
                <div className="operation-error" role="alert">
                  <strong>{opError.title}</strong>
                  {/* The service's advice for an account problem is to
                      reconnect, which the web client cannot do (D-017). */}
                  <span>{[opError.description, ACCOUNT_ERRORS.has(opError.code) ? "" : opError.solution].filter(Boolean).join(" ")}</span>
                </div>
              ) : null}
            </div>

            <Controls id={controlsId} open={filtersOpen} catalogue={feed.catalogue} filters={filters} sortMode={sortMode}
              onFilters={(next) => updateLocation({ filters: next, page: 0 })}
              onSort={(next) => updateLocation({ sort: next, page: 0 })} />

            <div className="feed-notices">
              <p className="feedback-notice" role="status">{surface === "discover" ? feedbackNotice : ""}</p>
              {feedbackError && surface === "discover" ? <div className="feedback-error" role="alert">
                <p>{feedbackError.message}</p>
                {feedbackError.retryable ? <button type="button" className="btn" disabled={pending} onClick={() => void vote(...feedbackError.vote)}>Retry decision</button> : null}
              </div> : null}
            </div>

            <section id="recommendations" tabIndex={-1} aria-label="Recommendations" aria-busy={firstFeedLoading || undefined} data-inspector-return="">
              {firstFeedLoading ? <FeedSkeleton /> : visibleCount === 0 || hideSampleFeed ? (
                exhausted && !hideSampleFeed ? (
                  <EmptyPanel icon="folder-watch-later" title="You’re all caught up"
                    message="Every pick in this analysis has been dealt with. Revisit what you saved for later, or refresh after your MAL list changes.">
                    {feed.state.watch_later_mal_ids.length ? <a className="btn" href="#/library">Review saved anime</a> : null}
                  </EmptyPanel>
                ) : isActive(filters) && !hideSampleFeed ? (
                  <EmptyPanel icon="search" title="No matches found"
                    message="Try clearing or widening the active filters to bring more anime back.">
                    <button type="button" className="btn" onClick={() => updateLocation({ filters: EMPTY_FILTERS, page: 0 })}>Clear filters</button>
                  </EmptyPanel>
                ) : (
                  <EmptyPanel icon="view-grid" title="No recommendations yet"
                    message="No recommendations are available for this profile yet." />
                )
              ) : (
                <FeedView view={view} models={pageItems} rankOffset={currentPage * PAGE_SIZE} caption={`Recommendations — ${visibleCount} in feed`}
                  watchLater={isSaved} hidden={isHidden} pending={pending} disabledReason={decisionsUnavailable}
                  trackActivity={surface === "discover" && view === "cards"}
                  onDetails={(model) => inspect(model, serverPaged ? pageItems : visible)} onExternal={external} onVote={vote} />
              )}
              {!firstFeedLoading && !hideSampleFeed ? <PageControls page={currentPage} total={visibleCount} onPageChange={changePage} label="Recommendations" /> : null}
            </section>
          </>
        ) : <><DiscoverHeader busy={busy || initialImporting} detail={progress?.message} />{state === "loading" || initialImporting ? <FeedSkeleton /> : null}</>}
      </main>
      </div>
      <main className="workspace-page" hidden={surface !== "library"}>
        {state === "loading" && !feed ? <FeedSkeleton /> : null}
        {state === "error" && error && surface === "library" ? <ErrorPanel error={error} onRetry={() => void reload()} /> : null}
        <LibraryPage feed={feed} pending={pending} disabledReason={decisionsUnavailable}
          notice={surface === "library" ? feedbackNotice : ""}
          error={surface === "library" && feedbackError ? { message: feedbackError.message, retry: feedbackError.retryable ? () => void vote(...feedbackError.vote) : null } : null}
          onVote={vote} onDetails={inspect} onExternal={external} />
      </main>
      {inspected && inspecting ? <ScoreInspector
        model={inspected}
        position={inspectedIndex + 1} total={inspecting.list.length}
        engineId={feedEngineId} watchLater={isSaved(inspecting.malId)} hidden={isHidden(inspecting.malId)}
        pending={pending} disabledReason={decisionsUnavailable}
        onPrevious={() => step(-1)} onNext={() => step(1)} onClose={() => setInspecting(null)}
        onVote={vote} onExternal={external} /> : null}
    </>
  );
}

function has(list: readonly number[] | undefined, malId: number | null): boolean {
  return malId !== null && !!list?.includes(malId);
}

/** The same set arithmetic RecommendationStateService.set_* performs. */
export function applyVote(
  state: LocalState,
  malId: number,
  action: Decision,
  value: boolean,
): LocalState {
  const add = (list: readonly number[]) => (list.includes(malId) ? [...list] : [...list, malId].sort((a, b) => a - b));
  const drop = (list: readonly number[]) => list.filter((item) => item !== malId);
  const set = (list: readonly number[]) => (value ? add(list) : drop(list));

  if (action === "watch_later") {
    return { ...state, watch_later_mal_ids: set(state.watch_later_mal_ids) };
  }
  return { ...state, hidden_mal_ids: set(state.hidden_mal_ids) };
}
