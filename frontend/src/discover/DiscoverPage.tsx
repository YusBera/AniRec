/**
 * Discover, against the real API.
 *
 * Qt equivalent: recommendation_page.py (2,637 lines) plus discover_page.py
 * (351) plus the parts of main_window.py that own the feed's operations.
 *
 * Votes are optimistic with a rollback, which the desktop does not need to
 * think about because a service call there is in-process. Over HTTP a vote is
 * a round trip, and waiting for it before repainting makes a button feel
 * broken. This is a real cost the boundary introduces, and it is contained to
 * one function.
 *
 * When the feed is ephemeral - the bundled sample library, which has no
 * profile directory to write to - votes are held in local state only. That is
 * exactly what _enter_demo_mode does with set_ephemeral(True).
 */

import { useCallback, useMemo, useRef, useState } from "react";
import { AniRecApiError, api } from "../api/client";
import { useFeed, useOperation } from "../api/hooks";
import type { LocalState, RecommendationViewModel } from "../api/types";
import { Controls } from "./Controls";
import { RecommendationCard, type Sentiment } from "./RecommendationCard";
import { RecommendationDetails } from "./RecommendationDetails";
import { rankingEngineId } from "./ScoreRail";
import { EMPTY_FILTERS, activeFilterCount, filterAndSort, isActive, type Filters, type SortMode } from "./filtering";
import { EmptyPanel, ErrorPanel, FeedSkeleton } from "./states";
import "./discover.css";
import { LibraryPage } from "../workspace/LibraryPage";
import { useRecommendationActivity } from "./useRecommendationActivity";

export function DiscoverPage({ surface = "discover" }: { surface?: "discover" | "library" | "inactive" }) {
  const { feed, state, error, reload, setFeed } = useFeed();
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [sortMode, setSortMode] = useState<SortMode>("personal-match");
  const [inspected, setInspected] = useState<RecommendationViewModel | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [feedbackNotice, setFeedbackNotice] = useState("");
  const [feedbackError, setFeedbackError] = useState<{ message: string; retryable: boolean; vote: [number, "watch_later" | "hidden", boolean] } | null>(null);
  const sentimentInFlight = useRef(new Set<number>());
  const [pendingSentiments, setPendingSentiments] = useState<Set<number>>(() => new Set());
  const [sentimentError, setSentimentError] = useState<{ message: string; retryable: boolean; vote: [number, Sentiment] } | null>(null);

  const operation = useOperation((finished) => {
    // A successful run replaces the feed; a cancel or failure leaves what is
    // on screen alone rather than blanking it.
    if (finished === "succeeded") void reload({ quiet: true });
  });

  const localState = feed?.state;
  const feedEngineId = feed ? rankingEngineId(feed.user_stats) : null;
  const activity = useRecommendationActivity(feed, inspected !== null || surface !== "discover");
  const inspect = (model: RecommendationViewModel) => {
    activity.record(model, "detail_open");
    setInspected(model);
  };

  const vote = useCallback(
    async (
      malId: number,
      action: "watch_later" | "hidden",
      value: boolean,
    ) => {
      // Responses contain the whole local state. Serialize writes so a late
      // response or rollback cannot erase another card's newer decision.
      if (!feed || savingRef.current || operation.status.state === "running") return;
      setFeedbackError(null);
      const title = feed.recommendations.find((model) => model.mal_id === malId)?.display_title ?? "Title";
      const outcome = action === "watch_later"
        ? (value ? "saved for later" : "removed from saved titles")
        : (value ? "set aside" : "restored to future feeds");
      const model = feed.recommendations.find((m) => m.mal_id === malId);
      const finishActivity = model && surface === "discover" ? activity.prepare(model, action === "watch_later" ? (value ? "watch_later_add" : "watch_later_remove") : (value ? "dismiss" : "restore")) : undefined;
      const previous = feed.state;
      const optimistic = applyVote(previous, malId, action, value);
      setFeed({ ...feed, state: optimistic });

      if (feed.ephemeral || !feed.state_profile_id) {
        setFeedbackNotice(`${title} ${outcome} in this preview. Changes reset on reload.`);
        return;
      }

      savingRef.current = true;
      setSaving(true);
      setFeedbackNotice(`Saving decision for ${title}…`);

      try {
        const response = await api.feedback({
          profile_id: feed.state_profile_id,
          mal_id: malId,
          action,
          value,
        });
        setFeed((current) => (current ? { ...current, state: response.state } : current));
        setFeedbackNotice(`${title} ${outcome}.`);
        finishActivity?.();
      } catch (caught) {
        // Roll back rather than leaving the card showing a vote the profile
        // does not have.
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
    [feed, setFeed, operation.status.state, activity.prepare, surface],
  );

  const saveSentiment = useCallback(async (malId: number, next: Sentiment) => {
    if (!feed || sentimentInFlight.current.has(malId) || operation.status.state === "running") return;
    const model = feed.recommendations.find((item) => item.mal_id === malId);
    const title = model?.display_title ?? "Title";
    const previous = sentimentFor(feed.state, malId);
    setSentimentError(null);
    setFeed((current) => current ? { ...current, state: applySentiment(current.state, malId, next) } : current);

    const outcome = next === "liked" ? "liked" : next === "disliked" ? "disliked" : "reaction cleared";
    if (feed.ephemeral || !feed.state_profile_id) {
      setFeedbackNotice(`${title}: ${outcome} in this preview. Changes reset on reload.`);
      return;
    }

    sentimentInFlight.current.add(malId);
    setPendingSentiments((current) => new Set(current).add(malId));
    setFeedbackNotice(`Saving vote for ${title}…`);
    try {
      const response = await api.feedback({
        profile_id: feed.state_profile_id,
        mal_id: malId,
        action: "sentiment",
        sentiment: next,
        feed_id: feed.activity_feed_id,
      });
      const confirmed = sentimentFor(response.state, malId);
      setFeed((current) => current ? { ...current, state: applySentiment(current.state, malId, confirmed) } : current);
      setFeedbackNotice(`${title}: ${outcome}. Votes are saved for evaluation and do not change recommendations yet.`);
    } catch (caught) {
      setFeed((current) => current ? { ...current, state: applySentiment(current.state, malId, previous) } : current);
      const detail = caught instanceof AniRecApiError ? caught.detail : null;
      setFeedbackNotice("");
      setSentimentError({
        message: `Vote for ${title} was not saved. ${detail ? [detail.title, detail.solution].filter(Boolean).join(". ") : "The service returned an unexpected response."} The previous reaction is restored.`,
        retryable: detail?.retryable ?? false,
        vote: [malId, next],
      });
    } finally {
      sentimentInFlight.current.delete(malId);
      setPendingSentiments((current) => {
        const updated = new Set(current);
        updated.delete(malId);
        return updated;
      });
    }
  }, [feed, operation.status.state, setFeed]);

  const visible = useMemo(
    () => (feed ? filterAndSort(feed.recommendations, filters, sortMode) : []),
    [feed, filters, sortMode],
  );

  const busy = operation.status.state === "running";
  const progress = operation.status.progress;
  const operationErrorText = operation.status.error
    ? [operation.status.error.title, operation.status.error.description, operation.status.error.solution].filter(Boolean).join(" ")
    : "";
  const staleFeed = operationErrorText.includes("Generate a new feed");

  return (
    <>
      <div hidden={surface !== "discover"}>
      <a className="skip-link" href="#recommendations">Skip to recommendations</a>
      <header className="titlebar">
        <div className="shell titlebar-inner">
          <span className="wordmark">
            Ani<span>Rec</span>
          </span>
          <h1 className="lbl">Discover</h1>
          <div className="tags">
            {feed?.source === "sample" ? (
              <span className="tag warn">Sample data</span>
            ) : null}
            {feed?.profile ? <span className="tag on">{feed.profile.username}</span> : null}
            <span className="tag">
              <span aria-hidden="true" className={`led ${busy ? "amber live" : "off"}`} /> Engine · {busy ? "Working" : state === "loading" ? "Loading" : state === "error" ? "Unavailable" : "Idle"}
            </span>
          </div>
        </div>
      </header>

      <main className="shell discover">
        <div className="ticks" aria-hidden="true" />

        {state === "error" && error ? (
          <ErrorPanel error={error} onRetry={() => void reload()} />
        ) : null}

        {feed ? (
          <>
            <details className="filter-drawer">
              <summary>Filters &amp; sort <span className="lbl">{activeFilterCount(filters)} active · {sortMode === "personal-match" ? "Personal fit" : sortMode === "mal-score" ? "MAL score" : sortMode}</span></summary>
              <Controls
              catalogue={feed.catalogue}
              filters={filters}
              sortMode={sortMode}
              onFilters={setFilters}
              onSort={setSortMode}
            />
            </details>

            <div className="statusbar">
              <span aria-hidden="true" className={`led ${busy ? "amber live" : ""}`} />
              <span className="count" role="status">
                <b>{visible.length}</b> of {feed.recommendations.length} shown
                {feed.hidden_count > 0 ? ` · ${feed.hidden_count} hidden` : ""}
              </span>
              <span className="spacer" />
              {busy ? (
                <button type="button" className="btn" onClick={() => void operation.cancel()}>
                  Cancel
                </button>
              ) : (
                <button
                  type="button"
                  className="btn primary"
                  disabled={feed.ephemeral || saving || pendingSentiments.size > 0}
                  title={
                    feed.ephemeral
                      ? "Connect a MyAnimeList profile to generate recommendations"
                      : undefined
                  }
                  onClick={() => void operation.start("more-recommendations", { count: 5 })}
                >
                  Recommend 5 more
                </button>
              )}
              {busy ? (
                <div className="progress-line">
                  <span className="lbl">{progress?.message ?? "Working"}</span>
                  <div
                    className={`progress-track${progress?.total ? "" : " indeterminate"}`}
                    role="progressbar"
                    aria-label={progress?.message ?? "Generating recommendations"}
                    aria-valuemin={0}
                    aria-valuemax={progress?.total || undefined}
                    aria-valuenow={progress?.total ? Math.max(0, Math.min(progress.current, progress.total)) : undefined}
                  >
                    <i
                      style={
                        progress?.total
                          ? { width: `${Math.max(0, Math.min(100, (progress.current / progress.total) * 100))}%` }
                          : undefined
                      }
                    />
                  </div>
                  <span className="lbl">
                    {progress?.total ? `${progress.current}/${progress.total}` : ""}
                  </span>
                </div>
              ) : null}
              {operation.status.error ? staleFeed ? (
                <div className="operation-error" role="alert">
                  <strong>{operation.status.error.title}</strong>
                  <span>{[operation.status.error.description, operation.status.error.solution].filter(Boolean).join(" ")}</span>
                  <button type="button" className="btn" disabled={saving || pendingSentiments.size > 0}
                    onClick={() => void operation.start("recommendation")}>Generate a new feed</button>
                </div>
              ) : (
                <span className="tag warn" role="alert">{operation.status.error.title}</span>
              ) : null}
            </div>

            <div className="feed-notices">
              {!feed.ephemeral && <details className="activity-controls">
                <summary>Recommendation activity</summary>
                <label><input type="checkbox" checked={activity.enabled} disabled={activity.pending || !activity.loaded}
                  onChange={(event) => void activity.setEnabled(event.target.checked)} /> Save activity on this device</label>
                <p>Records visible recommendations and your actions locally. Nothing is uploaded. Keeps up to 90 days and 50,000 events.</p>
                <button type="button" className="pill" disabled={activity.pending || !activity.loaded}
                  onClick={() => void activity.clear()}>Clear saved activity</button>
                <p role="status">{activity.notice}</p>
              </details>}
              {feed.ephemeral ? <p className="sample-note">Sample library. Decisions stay in this preview; connect a MyAnimeList profile in the desktop app to keep them and generate personal picks.</p> : null}
              <p className="feedback-notice" role="status">{feedbackNotice}</p>
              {feedbackError ? <div className="feedback-error" role="alert">
                <p>{feedbackError.message}</p>
                {feedbackError.retryable ? <button type="button" className="pill" disabled={saving || busy} onClick={() => void vote(...feedbackError.vote)}>Retry decision</button> : null}
              </div> : null}
              {sentimentError ? <div className="feedback-error" role="alert">
                <p>{sentimentError.message}</p>
                {sentimentError.retryable ? <button type="button" className="pill" disabled={busy || pendingSentiments.has(sentimentError.vote[0])}
                  onClick={() => void saveSentiment(...sentimentError.vote)}>Retry vote</button> : null}
              </div> : null}
            </div>

            <section id="recommendations" tabIndex={-1} aria-label="Recommendations">

            {visible.length === 0 ? (
              <EmptyPanel
                filtered={isActive(filters)}
                onClear={() => setFilters(EMPTY_FILTERS)}
              />
            ) : (
              <div className="feed">
                {visible.map((model) => (
                  <RecommendationCard
                    key={model.mal_id ?? model.display_title}
                    model={model}
                    rankingEngineId={feedEngineId}
                    pending={saving || busy}
                    sentimentPending={model.mal_id !== null && pendingSentiments.has(model.mal_id)}
                    onDetails={inspect}
                    onExternal={(model) => { if (surface === "discover") activity.record(model, "external_open"); }}
                    watchLater={has(localState?.watch_later_mal_ids, model.mal_id)}
                    hidden={has(localState?.hidden_mal_ids, model.mal_id)}
                    sentiment={sentimentFor(localState, model.mal_id)}
                    onVote={vote}
                    onSentiment={saveSentiment}
                  />
                ))}
              </div>
            )}
            </section>
          </>
        ) : state === "loading" ? (
          <FeedSkeleton />
        ) : null}
      </main>
      </div>
      <main className="workspace-page" hidden={surface !== "library"}>
        <h1 tabIndex={-1}>My Library</h1>
        <p className="workspace-intro">Saved recommendation decisions, with the evidence attached.</p>
        {feed?.ephemeral ? <p className="sample-note">Sample data. Decisions reset on reload.</p> : null}
        {state === "loading" && !feed ? <FeedSkeleton /> : null}
        {state === "error" && error ? <ErrorPanel error={error} onRetry={() => void reload()} /> : null}
        <p role="status">{surface === "library" ? (feed?.ephemeral ? feedbackNotice.replace(" in this preview. Changes reset on reload.", ".") : feedbackNotice) : ""}</p>
        {feedbackError ? <div role="alert"><p>{feedbackError.message}</p>{feedbackError.retryable ? <button className="btn" disabled={saving || busy} onClick={() => void vote(...feedbackError.vote)}>Retry decision</button> : null}</div> : null}
        {feed ? <LibraryPage feed={feed} pending={saving || busy} onVote={vote} onDetails={setInspected} /> : null}
      </main>
      {inspected ? <RecommendationDetails model={inspected} engineId={feedEngineId} onClose={() => setInspected(null)} onExternal={(model) => { if (surface === "discover") activity.record(model, "external_open"); }} /> : null}
    </>
  );
}

function has(list: number[] | undefined, malId: number | null): boolean {
  return malId !== null && !!list?.includes(malId);
}

function sentimentFor(state: LocalState | undefined, malId: number | null): Sentiment {
  if (malId === null || !state) return null;
  if (state.liked_mal_ids.includes(malId)) return "liked";
  if (state.disliked_mal_ids.includes(malId)) return "disliked";
  return null;
}

export function applySentiment(state: LocalState, malId: number, sentiment: Sentiment): LocalState {
  const add = (list: number[]) => (list.includes(malId) ? list : [...list, malId].sort((a, b) => a - b));
  const drop = (list: number[]) => list.filter((item) => item !== malId);
  return {
    ...state,
    liked_mal_ids: sentiment === "liked" ? add(state.liked_mal_ids) : drop(state.liked_mal_ids),
    disliked_mal_ids: sentiment === "disliked" ? add(state.disliked_mal_ids) : drop(state.disliked_mal_ids),
  };
}

/** The same set arithmetic RecommendationStateService.set_* performs. */
export function applyVote(
  state: LocalState,
  malId: number,
  action: "watch_later" | "hidden",
  value: boolean,
): LocalState {
  const add = (list: number[]) => (list.includes(malId) ? list : [...list, malId].sort((a, b) => a - b));
  const drop = (list: number[]) => list.filter((item) => item !== malId);
  const set = (list: number[]) => (value ? add(list) : drop(list));

  if (action === "watch_later") {
    return { ...state, watch_later_mal_ids: set(state.watch_later_mal_ids) };
  }
  return { ...state, hidden_mal_ids: set(state.hidden_mal_ids) };
}
