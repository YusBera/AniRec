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
import { useFeed, useOperation } from "../api/hooks";
import type { Feed, LocalState, RecommendationViewModel } from "../api/types";
import { Icon } from "../assets/Icon";
import { Controls } from "./Controls";
import { DiscoverHeader, type HeaderState } from "./DiscoverHeader";
import { FeedView, ViewToggle, type ViewMode } from "./FeedViews";
import type { Decision } from "./RecommendationCard";
import { ScoreInspector } from "./ScoreInspector";
import { rankingEngineId } from "./ScoreRail";
import { EMPTY_FILTERS, activeFilterCount, filterAndSort, isActive, type Filters, type SortMode } from "./filtering";
import { EmptyPanel, ErrorPanel, FeedSkeleton } from "./states";
import "./discover.css";
import { LibraryPage } from "../workspace/LibraryPage";
import { PAGE_SIZE, PageControls } from "../workspace/common";
import { useRecommendationActivity } from "./useRecommendationActivity";

export const NO_PROFILE_REASON = "Connect or select a profile to manage local recommendation lists.";
export const RUN_UNAVAILABLE = "Personal analysis needs a connected profile. Connecting an account is not available in the web client yet.";

interface Inspecting {
  malId: number | null;
  title: string;
  list: RecommendationViewModel[];
}

/** The control bar's summary, in the desktop's vocabulary (`_update_feedback_summary`). */
export function feedbackSummary(feed: Feed): string {
  const saved = feed.state.watch_later_mal_ids.length;
  const setAside = feed.state.hidden_mal_ids.length;
  if (feed.ephemeral) return `SAMPLE · ${saved} SAVED · ${setAside} SET ASIDE · CONNECT TO KEEP`;
  if (!feed.state_profile_id) return "NO PROFILE · LISTS DISABLED";
  if (!saved && !setAside) return "PROFILE READY · SAVE OR SET ASIDE TO SHAPE THE FEED";
  return `LISTS SAVED · ${saved} SAVED · ${setAside} SET ASIDE`;
}

export function DiscoverPage({ surface = "discover", onFeedChange, onOperationStarted }: {
  surface?: "discover" | "library" | "inactive";
  /** Lets the shell report SOURCE and the sample banner from the same feed. */
  onFeedChange?: (feed: Feed | null) => void;
  /** Lets the shell refresh ENGINE and ACTIVITY as soon as a run starts. */
  onOperationStarted?: () => void;
}) {
  const [showHidden, setShowHidden] = useState(false);
  // A profile feed asks the service for its Not interested titles. The sample
  // feed must not be refetched: its decisions live only in this page, and a
  // reload would silently discard them.
  const [fetchHidden, setFetchHidden] = useState(false);
  const { feed, state, error, reload, setFeed } = useFeed(fetchHidden);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [sortMode, setSortMode] = useState<SortMode>("personal-match");
  const [view, setView] = useState<ViewMode>("cards");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(0);
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

  const feedRef = useRef(onFeedChange);
  feedRef.current = onFeedChange;
  useEffect(() => { feedRef.current?.(feed); }, [feed]);

  const localState = feed?.state;
  const feedEngineId = feed ? rankingEngineId(feed.user_stats) : null;
  const activity = useRecommendationActivity(feed, inspecting !== null || surface !== "discover" || view !== "cards");
  const busy = operation.status.state === "running";
  const pending = saving || busy;
  const decisionsUnavailable = feed && !feed.ephemeral && !feed.state_profile_id ? NO_PROFILE_REASON : undefined;
  const runUnavailable = !feed || feed.ephemeral || !feed.state_profile_id ? RUN_UNAVAILABLE : null;

  const inspect = (model: RecommendationViewModel, list: RecommendationViewModel[]) => {
    if (surface === "discover") activity.record(model, "detail_open");
    setInspecting({ malId: model.mal_id, title: model.display_title, list });
  };

  const vote = useCallback(
    async (malId: number, action: Decision, value: boolean) => {
      if (!feed || savingRef.current || operation.status.state === "running") return;
      setFeedbackError(null);
      const model = feed.recommendations.find((m) => m.mal_id === malId)
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
    [feed, setFeed, operation.status.state, activity.prepare, surface, inspecting],
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
  useEffect(() => setPage(0), [feed?.activity_feed_id]);
  const currentPage = Math.min(page, Math.max(0, Math.ceil(visible.length / PAGE_SIZE) - 1));
  const pageItems = visible.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  const changePage = (next: number) => {
    setPage(next);
    document.getElementById("recommendations")?.focus();
  };

  const progress = operation.status.progress;
  const opError = operation.status.error;
  const staleFeed = opError ? [opError.title, opError.description, opError.solution].join(" ").includes("Generate a new feed") : false;
  const running = busy && operation.status.kind === "recommendation";
  const headerState: HeaderState = busy ? "busy" : operation.status.state === "failed" ? "fault" : "ready";
  const headerMessage = busy ? progress?.message ?? "Working…"
    : opError ? [opError.title, opError.description].filter(Boolean).join(". ")
      : runUnavailable ?? "";
  const start = (kind: string, payload: Record<string, unknown> = {}) => {
    void operation.start(kind, payload).then(() => onOperationStarted?.());
  };
  const hiddenInFeed = feed ? feed.recommendations.some((m) => has(feed.state.hidden_mal_ids, m.mal_id)) : false;
  const exhausted = !!feed && !visible.length && !isActive(filters) && feed.recommendations.length > 0 && !showHidden;

  // The inspector walks the list it was opened from.
  const inspectedIndex = inspecting ? inspecting.list.findIndex((m) => m.mal_id === inspecting.malId && m.display_title === inspecting.title) : -1;
  const inspected = inspecting && inspectedIndex >= 0 ? inspecting.list[inspectedIndex]! : null;
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
        <DiscoverHeader state={headerState} message={headerMessage} running={running}
          runDisabledReason={busy ? null : runUnavailable} taste={feed?.taste_vector}
          onRun={() => start("recommendation")} />

        {state === "error" && error ? <ErrorPanel error={error} onRetry={() => void reload()} /> : null}

        {feed ? (
          <>
            <div className="control-bar">
              <p className="control-readout" role="status">
                <span className="readout-count">{visible.length} IN FEED</span>
                <span className="strip-rule" aria-hidden="true" />
                <span>{feedbackSummary(feed)}</span>
              </p>
              <div className="control-actions">
                {busy ? (
                  <button type="button" className="btn" onClick={() => void operation.cancel()}>Cancel</button>
                ) : (
                  <button type="button" className="btn" disabled={!!runUnavailable || saving}
                    title={runUnavailable ?? "Generate five more unseen picks from the same ranking."}
                    onClick={() => start("more-recommendations", { count: 5 })}>Recommend 5 more</button>
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
                  <input type="checkbox" checked={showHidden} onChange={(event) => {
                    setShowHidden(event.target.checked);
                    if (!feed.ephemeral) setFetchHidden(event.target.checked);
                  }} /> Show not interested
                </label> : null}
                <ViewToggle view={view} onChange={setView} />
              </div>
              {busy ? (
                <div className="progress-line">
                  <span className="lbl">{progress?.message ?? "Working…"}</span>
                  <div className={`progress-track${progress?.total ? "" : " indeterminate"}`} role="progressbar"
                    aria-label={progress?.message ?? "Generating recommendations"} aria-valuemin={0}
                    aria-valuemax={progress?.total || undefined}
                    aria-valuenow={progress?.total ? Math.max(0, Math.min(progress.current, progress.total)) : undefined}>
                    <i style={progress?.total ? { width: `${Math.max(0, Math.min(100, (progress.current / progress.total) * 100))}%` } : undefined} />
                  </div>
                  <span className="lbl">{progress?.total ? `${progress.current}/${progress.total}` : ""}</span>
                </div>
              ) : null}
              {opError ? staleFeed ? (
                <div className="operation-error" role="alert">
                  <strong>{opError.title}</strong>
                  <span>{[opError.description, opError.solution].filter(Boolean).join(" ")}</span>
                  <button type="button" className="btn" disabled={saving} onClick={() => start("recommendation")}>Generate a new feed</button>
                </div>
              ) : (
                <div className="operation-error" role="alert">
                  <strong>{opError.title}</strong>
                  <span>{[opError.description, opError.solution].filter(Boolean).join(" ")}</span>
                </div>
              ) : null}
            </div>

            <Controls id={controlsId} open={filtersOpen} catalogue={feed.catalogue} filters={filters} sortMode={sortMode}
              onFilters={(next) => { setFilters(next); setPage(0); }}
              onSort={(next) => { setSortMode(next); setPage(0); }} />

            <div className="feed-notices">
              {feed.ephemeral ? <p className="sample-note">Sample library. Decisions reset on reload.</p> : null}
              <p className="feedback-notice" role="status">{surface === "discover" ? feedbackNotice : ""}</p>
              {feedbackError && surface === "discover" ? <div className="feedback-error" role="alert">
                <p>{feedbackError.message}</p>
                {feedbackError.retryable ? <button type="button" className="btn" disabled={pending} onClick={() => void vote(...feedbackError.vote)}>Retry decision</button> : null}
              </div> : null}
            </div>

            <section id="recommendations" tabIndex={-1} aria-label="Recommendations">
              {visible.length === 0 ? (
                exhausted ? (
                  <EmptyPanel icon="folder-watch-later" title="You’re all caught up"
                    message="Every current pick has been dealt with. Generate 10 fresh anime, or revisit what you saved for later.">
                    {feed.state.watch_later_mal_ids.length ? <a className="btn" href="#/library">Review saved anime</a> : null}
                    <button type="button" className="btn primary" disabled={!!runUnavailable || pending} title={runUnavailable ?? undefined}
                      onClick={() => start("more-recommendations", { count: 10 })}>Recommend 10 new anime</button>
                  </EmptyPanel>
                ) : isActive(filters) ? (
                  <EmptyPanel icon="search" title="No matches found"
                    message="Try clearing or widening the active filters to bring more anime back.">
                    <button type="button" className="btn" onClick={() => { setFilters(EMPTY_FILTERS); setPage(0); }}>Clear filters</button>
                  </EmptyPanel>
                ) : (
                  <EmptyPanel icon="view-grid" title="Build your first feed"
                    message={runUnavailable ? "No recommendations are available yet. A personal feed needs a connected profile." : "Choose RUN ANALYSIS to create a personal anime feed."} />
                )
              ) : (
                <FeedView view={view} models={pageItems} caption={`Recommendations — ${visible.length} in feed`}
                  watchLater={isSaved} hidden={isHidden} pending={pending} disabledReason={decisionsUnavailable}
                  trackActivity={surface === "discover" && view === "cards"}
                  onDetails={(model) => inspect(model, visible)} onExternal={external} onVote={vote} />
              )}
              <PageControls page={currentPage} total={visible.length} onPageChange={changePage} label="Recommendations" />
            </section>
          </>
        ) : state === "loading" ? (
          <FeedSkeleton />
        ) : null}
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
