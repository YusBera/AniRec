/**
 * My Library: the explorer again, over the two collections a reader files.
 *
 * Qt equivalent: `RecommendationExplorerPage` shown with
 * `LIBRARY_STATES = ("watch-later", "not-interested")` - Watch Later first,
 * then Not interested - with the same Cards / List / Table views and the
 * per-collection empty states from `_show_current_view`.
 *
 * Saved IDs outside the current feed resolve from local snapshots, or on
 * request from MAL. An ID that cannot be resolved is listed as an ID; no
 * title, cover or score is invented for it.
 */

import { useEffect, useRef, useState } from "react";
import { api, AniRecApiError } from "../api/client";
import type { Feed, RecommendationViewModel } from "../api/types";
import { FeedView, ViewToggle, type ViewMode } from "../discover/FeedViews";
import type { Decision } from "../discover/RecommendationCard";
import { EmptyPanel } from "../discover/states";
import { PageHeading, PAGE_SIZE, PageControls } from "./common";

type Collection = "watch_later" | "hidden";

const COLLECTIONS: { id: Collection; label: string; heading: string }[] = [
  { id: "watch_later", label: "Watch Later", heading: "Watch Later" },
  { id: "hidden", label: "Not interested", heading: "Not interested" },
];

export function LibraryPage({ feed, pending, disabledReason, notice = "", error = null, onVote, onDetails, onExternal }: {
  feed: Feed | null;
  pending: boolean;
  disabledReason?: string;
  notice?: string;
  error?: { message: string; retry: (() => void) | null } | null;
  onVote: (id: number, action: Decision, value: boolean, model?: RecommendationViewModel) => void;
  onDetails: (model: RecommendationViewModel, list: RecommendationViewModel[]) => void;
  onExternal?: (model: RecommendationViewModel) => void;
}) {
  const [collection, setCollection] = useState<Collection>("watch_later");
  const [view, setView] = useState<ViewMode>("cards");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [missingPage, setMissingPage] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const [extra, setExtra] = useState<RecommendationViewModel[]>([]);
  const [loadError, setLoadError] = useState("");
  const [resolving, setResolving] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);
  const profileId = !feed || feed.ephemeral ? null : feed.state_profile_id;
  const currentProfile = useRef(profileId);
  currentProfile.current = profileId;
  useEffect(() => {
    let cancelled = false;
    setExtra([]); setLoadError(""); setResolving(null);
    if (profileId) api.library(profileId).then(value => {
      if (!cancelled && value.profile_id === profileId) setExtra([...(value.recommendations ?? [])]);
    }).catch(() => { if (!cancelled) setLoadError("Saved title details could not be loaded. Try again."); });
    return () => { cancelled = true; };
  }, [profileId, attempt]);
  const resolve = async (id: number) => {
    if (!profileId) return;
    setResolving(id); setLoadError("");
    try { const model = await api.resolveTitle(profileId, id); if (currentProfile.current === profileId) setExtra(previous => [...previous.filter(m => m.mal_id !== id), model]); }
    catch (caught) { if (currentProfile.current === profileId) setLoadError(caught instanceof AniRecApiError ? `${caught.detail.description} ${caught.detail.solution}` : "Title details could not be loaded. Try again."); }
    finally { if (currentProfile.current === profileId) setResolving(null); }
  };

  const state = feed?.state;
  const ids = !state ? [] : collection === "watch_later" ? state.watch_later_mal_ids : state.hidden_mal_ids;
  const recommendations = feed?.recommendations ?? [];
  const available = [...recommendations, ...extra.filter(m => !recommendations.some(current => current.mal_id === m.mal_id))];
  const models = available.filter(m => m.mal_id !== null && ids.includes(m.mal_id));
  const shown = models.filter(m => m.display_title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const missing = ids.filter(id => !models.some(m => m.mal_id === id));
  const currentPage = Math.min(page, Math.max(0, Math.ceil(shown.length / PAGE_SIZE) - 1));
  const pageItems = shown.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  const currentMissingPage = Math.min(missingPage, Math.max(0, Math.ceil(missing.length / PAGE_SIZE) - 1));
  const missingItems = missing.slice(currentMissingPage * PAGE_SIZE, (currentMissingPage + 1) * PAGE_SIZE);
  const changePage = (next: number) => { setPage(next); heading.current?.focus(); };
  const undo = (id: number) => { onVote(id, collection, false); heading.current?.focus(); };
  const inSet = (list: readonly number[] | undefined) => (malId: number | null) => malId !== null && !!list?.includes(malId);
  const active = COLLECTIONS.find(item => item.id === collection)!;

  return <>
    <PageHeading name="My Library" />
    <p className="workspace-intro">Everything you have saved, or passed on.</p>
    <p role="status" className="feedback-notice">{feed?.ephemeral ? notice.replace(" in this preview. Changes reset on reload.", ".") : notice}</p>
    {error ? <div className="feedback-error" role="alert"><p>{error.message}</p>{error.retry ? <button className="btn" disabled={pending} onClick={error.retry}>Retry decision</button> : null}</div> : null}
    {loadError ? <div role="alert" className="feedback-error"><p>{loadError}</p><button className="btn" onClick={() => setAttempt(value => value + 1)}>Reload saved details</button></div> : null}

    <div className="library-tabs" role="group" aria-label="Library collection">
      {COLLECTIONS.map(item => {
        const count = !state ? 0 : item.id === "watch_later" ? state.watch_later_mal_ids.length : state.hidden_mal_ids.length;
        return <button key={item.id} type="button" className="library-tab" aria-pressed={collection === item.id}
          aria-label={`${item.heading} · ${count}`}
          onClick={() => { setCollection(item.id); setPage(0); setMissingPage(0); }}>
          {item.label} <span className="tab-count">{count}</span>
        </button>;
      })}
    </div>
    <div className="control-bar library-bar">
      <div className="control-actions">
        <label className="library-search">Find a saved title<input type="search" value={query} onChange={e => { setQuery(e.target.value); setPage(0); }} /></label>
        <ViewToggle view={view} onChange={setView} />
      </div>
    </div>
    <h2 ref={heading} tabIndex={-1} className="collection-heading" data-inspector-return="">{active.heading} <small>{shown.length} matching</small></h2>
    {ids.length === 0 ? (collection === "watch_later"
      ? <EmptyPanel icon="folder-watch-later" title="Your Watch Later list is empty" message="Save an anime from any card and it will appear in this collection.">
          <a className="btn" href="#/discover">Explore Discover</a>
        </EmptyPanel>
      : <EmptyPanel icon="folder-not-interested" title="Nothing set aside yet" message="Anime you mark Not interested stay here, out of the feed, and can be brought back at any time." />)
      : !shown.length && !missing.length ? <EmptyPanel icon="search" title="No matches found" message="No saved title matches this search.">
          <button className="btn" onClick={() => setQuery("")}>Clear search</button>
        </EmptyPanel> : null}
    {pageItems.length ? <FeedView view={view} models={pageItems} rankOffset={currentPage * PAGE_SIZE} caption={`${active.heading} — ${shown.length} saved titles`}
      watchLater={inSet(state?.watch_later_mal_ids)} hidden={inSet(state?.hidden_mal_ids)} pending={pending} disabledReason={disabledReason}
      onDetails={model => onDetails(model, shown)} onExternal={onExternal} onVote={onVote} /> : null}
    <PageControls page={currentPage} total={shown.length} onPageChange={changePage} label="Saved titles" />
    {missing.length ? <section className="workspace-message"><h3>Saved decisions outside this feed</h3><p>Title details for these MyAnimeList IDs are absent from the available snapshots.</p>{missingItems.map(id => <p key={id}>MAL #{id} {profileId ? <button className="btn" disabled={resolving !== null} onClick={() => void resolve(id)}>{resolving === id ? "Loading…" : "Load details from MAL"}</button> : null} <button className="btn" disabled={pending} onClick={() => undo(id)}>{collection === "watch_later" ? "Remove saved decision" : "Show again"}</button></p>)}<PageControls page={currentMissingPage} total={missing.length} onPageChange={next => { setMissingPage(next); heading.current?.focus(); }} label="Unresolved saved IDs" /></section> : null}
  </>;
}
