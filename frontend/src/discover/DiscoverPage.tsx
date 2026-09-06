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
import { RecommendationCard } from "./RecommendationCard";
import { RecommendationDetails } from "./RecommendationDetails";
import { EMPTY_FILTERS, activeFilterCount, filterAndSort, isActive, type Filters, type SortMode } from "./filtering";
import { EmptyPanel, ErrorPanel, FeedSkeleton } from "./states";
import "./discover.css";

export function DiscoverPage() {
  const { feed, state, error, reload, setFeed } = useFeed();
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [sortMode, setSortMode] = useState<SortMode>("personal-match");
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [inspected, setInspected] = useState<RecommendationViewModel | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [feedbackNotice, setFeedbackNotice] = useState("");
  const [feedbackError, setFeedbackError] = useState<{ message: string; retryable: boolean; vote: [number, "watch_later" | "hidden", boolean] } | null>(null);

  const operation = useOperation((finished) => {
    // A successful run replaces the feed; a cancel or failure leaves what is
    // on screen alone rather than blanking it.
    if (finished === "succeeded") void reload({ quiet: true });
  });

  const localState = feed?.state;

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
    [feed, setFeed, operation.status.state],
  );

  const visible = useMemo(
    () => (feed ? filterAndSort(feed.recommendations, filters, sortMode) : []),
    [feed, filters, sortMode],
  );

  const busy = operation.status.state === "running";
  const progress = operation.status.progress;

  return (
    <>
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
              <summary>Filters &amp; sort <span className="lbl">{activeFilterCount(filters)} active · {sortMode === "personal-match" ? "Personal match" : sortMode === "mal-score" ? "MAL score" : sortMode}</span></summary>
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
              <button
                type="button"
                className="pill"
                aria-pressed={showBreakdown}
                onClick={() => setShowBreakdown((current) => !current)}
              >
                Breakdown
              </button>
              {busy ? (
                <button type="button" className="btn" onClick={() => void operation.cancel()}>
                  Cancel
                </button>
              ) : (
                <button
                  type="button"
                  className="btn primary"
                  disabled={feed.ephemeral || saving}
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
              {operation.status.error ? (
                <span className="tag warn" role="alert">{operation.status.error.title}</span>
              ) : null}
            </div>

            <div className="feed-notices">
              {feed.ephemeral ? <p className="sample-note">Sample library. Decisions stay in this preview; connect a MyAnimeList profile in the desktop app to keep them and generate personal picks.</p> : null}
              <p className="feedback-notice" role="status">{feedbackNotice}</p>
              {feedbackError ? <div className="feedback-error" role="alert">
                <p>{feedbackError.message}</p>
                {feedbackError.retryable ? <button type="button" className="pill" disabled={saving || busy} onClick={() => void vote(...feedbackError.vote)}>Retry decision</button> : null}
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
                    showBreakdown={showBreakdown}
                    pending={saving || busy}
                    onDetails={setInspected}
                    watchLater={has(localState?.watch_later_mal_ids, model.mal_id)}
                    hidden={has(localState?.hidden_mal_ids, model.mal_id)}
                    onVote={vote}
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
      {inspected ? <RecommendationDetails model={inspected} onClose={() => setInspected(null)} /> : null}
    </>
  );
}

function has(list: number[] | undefined, malId: number | null): boolean {
  return malId !== null && !!list?.includes(malId);
}

/** The same set arithmetic RecommendationStateService.set_* performs. */
export function applyVote(
  state: LocalState,
  malId: number,
  action: "sentiment" | "watch_later" | "hidden",
  value: boolean,
): LocalState {
  const add = (list: number[]) => (list.includes(malId) ? list : [...list, malId].sort((a, b) => a - b));
  const drop = (list: number[]) => list.filter((item) => item !== malId);
  const set = (list: number[]) => (value ? add(list) : drop(list));

  if (action === "watch_later") {
    return { ...state, watch_later_mal_ids: set(state.watch_later_mal_ids) };
  }
  if (action === "hidden") {
    return { ...state, hidden_mal_ids: set(state.hidden_mal_ids) };
  }
  // Sentiment is mutually exclusive: liking clears a dislike.
  return {
    ...state,
    liked_mal_ids: set(state.liked_mal_ids),
    disliked_mal_ids: value ? drop(state.disliked_mal_ids) : state.disliked_mal_ids,
  };
}
