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

import { useCallback, useMemo, useState } from "react";
import { AniRecApiError, api } from "../api/client";
import { useFeed, useOperation } from "../api/hooks";
import type { LocalState } from "../api/types";
import { Controls } from "./Controls";
import { RecommendationCard } from "./RecommendationCard";
import { EMPTY_FILTERS, filterAndSort, isActive, type Filters, type SortMode } from "./filtering";
import { EmptyPanel, ErrorPanel, FeedSkeleton } from "./states";
import "./discover.css";

export function DiscoverPage() {
  const { feed, state, error, reload, setFeed } = useFeed();
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [sortMode, setSortMode] = useState<SortMode>("personal-match");
  const [showBreakdown, setShowBreakdown] = useState(false);

  const operation = useOperation((finished) => {
    // A successful run replaces the feed; a cancel or failure leaves what is
    // on screen alone rather than blanking it.
    if (finished === "succeeded") void reload({ quiet: true });
  });

  const localState = feed?.state;

  const vote = useCallback(
    async (
      malId: number,
      action: "sentiment" | "watch_later" | "hidden",
      value: boolean,
    ) => {
      if (!feed) return;
      const previous = feed.state;
      const optimistic = applyVote(previous, malId, action, value);
      setFeed({ ...feed, state: optimistic });

      if (feed.ephemeral || !feed.state_profile_id) return;

      try {
        const response = await api.feedback({
          profile_id: feed.state_profile_id,
          mal_id: malId,
          action,
          value,
          sentiment: action === "sentiment" ? (value ? "liked" : null) : undefined,
        });
        setFeed((current) => (current ? { ...current, state: response.state } : current));
      } catch (caught) {
        // Roll back rather than leaving the card showing a vote the profile
        // does not have.
        setFeed((current) => (current ? { ...current, state: previous } : current));
        if (!(caught instanceof AniRecApiError)) throw caught;
      }
    },
    [feed, setFeed],
  );

  const visible = useMemo(
    () => (feed ? filterAndSort(feed.recommendations, filters, sortMode) : []),
    [feed, filters, sortMode],
  );

  const busy = operation.status.state === "running";
  const progress = operation.status.progress;

  return (
    <>
      <header className="titlebar">
        <div className="shell titlebar-inner">
          <span className="wordmark">
            Ani<span>Rec</span>
          </span>
          <span className="lbl">Discover</span>
          <div className="tags">
            {feed?.source === "sample" ? (
              <span className="tag warn">Sample data</span>
            ) : null}
            {feed?.profile ? <span className="tag on">{feed.profile.username}</span> : null}
            <span className="tag">
              <span className={`led ${busy ? "amber live" : "off"}`} /> Engine
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
            <Controls
              catalogue={feed.catalogue}
              filters={filters}
              sortMode={sortMode}
              onFilters={setFilters}
              onSort={setSortMode}
            />

            <div className="statusbar">
              <span className={`led ${busy ? "amber live" : ""}`} />
              <span className="count">
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
                  disabled={feed.ephemeral}
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
                  >
                    <i
                      style={
                        progress?.total
                          ? { width: `${(progress.current / progress.total) * 100}%` }
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
                <span className="tag warn">{operation.status.error.title}</span>
              ) : null}
            </div>

            {visible.length === 0 ? (
              <EmptyPanel
                filtered={isActive(filters)}
                onClear={() => setFilters(EMPTY_FILTERS)}
              />
            ) : (
              <div className="feed">
                {visible.map((model, index) => (
                  <RecommendationCard
                    key={model.mal_id ?? model.display_title}
                    model={model}
                    index={index}
                    showBreakdown={showBreakdown}
                    liked={has(localState?.liked_mal_ids, model.mal_id)}
                    disliked={has(localState?.disliked_mal_ids, model.mal_id)}
                    watchLater={has(localState?.watch_later_mal_ids, model.mal_id)}
                    hidden={has(localState?.hidden_mal_ids, model.mal_id)}
                    onVote={vote}
                  />
                ))}
              </div>
            )}
          </>
        ) : state === "loading" ? (
          <FeedSkeleton />
        ) : null}
      </main>
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
