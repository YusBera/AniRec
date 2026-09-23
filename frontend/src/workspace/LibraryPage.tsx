import { useEffect, useRef, useState } from "react";
import { api, AniRecApiError } from "../api/client";
import type { Feed, RecommendationViewModel } from "../api/types";
import { personalFitText, rankingEngineId } from "../discover/ScoreRail";
import { Genres, Poster } from "./common";

export function LibraryPage({ feed, pending, onVote, onDetails }: {
  feed: Feed; pending: boolean;
  onVote: (id: number, action: "watch_later" | "hidden", value: boolean) => void;
  onDetails: (model: RecommendationViewModel) => void;
}) {
  const [collection, setCollection] = useState<"watch_later" | "hidden">("watch_later");
  const [view, setView] = useState("cards");
  const [query, setQuery] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const [extra, setExtra] = useState<RecommendationViewModel[]>([]);
  const [loadError, setLoadError] = useState("");
  const [resolving, setResolving] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);
  const profileId = feed.ephemeral ? null : feed.state_profile_id;
  const feedEngineId = rankingEngineId(feed.user_stats);
  const currentProfile = useRef(profileId);
  currentProfile.current = profileId;
  useEffect(() => {
    let cancelled = false;
    setExtra([]); setLoadError(""); setResolving(null);
    if (profileId) api.library(profileId).then(value => {
      if (!cancelled && value.profile_id === profileId) setExtra(value.recommendations ?? []);
    }).catch(() => { if (!cancelled) setLoadError("Saved title details could not be loaded. Try again."); });
    return () => { cancelled = true; };
  }, [profileId, attempt]);
  const resolve = async (id: number) => {
    if (!profileId) return;
    setResolving(id); setLoadError("");
    try { const model = await api.resolveTitle(profileId, id); if (currentProfile.current === profileId) setExtra(previous => [...previous.filter(m => m.mal_id !== id), model]); }
    catch (error) { if (currentProfile.current === profileId) setLoadError(error instanceof AniRecApiError ? `${error.detail.description} ${error.detail.solution}` : "Title details could not be loaded. Try again."); }
    finally { if (currentProfile.current === profileId) setResolving(null); }
  };
  const ids = collection === "watch_later" ? feed.state.watch_later_mal_ids : feed.state.hidden_mal_ids;
  const available = [...feed.recommendations, ...extra.filter(m => !feed.recommendations.some(current => current.mal_id === m.mal_id))];
  const models = available.filter(m => m.mal_id !== null && ids.includes(m.mal_id));
  const shown = models.filter(m => m.display_title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const missing = ids.filter(id => !models.some(m => m.mal_id === id));
  const undo = (id: number) => { onVote(id, collection, false); heading.current?.focus(); };
  return <>
    {loadError ? <div role="alert"><p>{loadError}</p><button className="btn" onClick={() => setAttempt(value => value + 1)}>Reload saved details</button></div> : null}
    <div className="workspace-toolbar" aria-label="Library collection">
      <button className="btn" aria-pressed={collection === "watch_later"} onClick={() => setCollection("watch_later")}>Watch Later · {feed.state.watch_later_mal_ids.length}</button>
      <button className="btn" aria-pressed={collection === "hidden"} onClick={() => setCollection("hidden")}>Not interested · {feed.state.hidden_mal_ids.length}</button>
    </div>
    <div className="workspace-toolbar">
      <label>Find a saved title<input type="search" value={query} onChange={e => setQuery(e.target.value)} /></label>
      <label>View<select value={view} onChange={e => setView(e.target.value)}><option value="cards">Cards</option><option value="list">List</option><option value="table">Table</option></select></label>
    </div>
    <h2 ref={heading} tabIndex={-1}>{collection === "watch_later" ? "Saved for later" : "Set aside"} <small>{shown.length} shown</small></h2>
    {ids.length === 0 ? <div className="workspace-empty"><h3>{collection === "watch_later" ? "Your Watch Later list is empty" : "No titles set aside"}</h3><p>Choose a title in Discover to add it to this collection.</p><a className="btn" href="#/discover">Explore Discover</a></div>
      : !shown.length && !missing.length ? <p>No saved titles match this search. <button className="btn" onClick={() => setQuery("")}>Clear search</button></p> : null}
    {view === "table" ? <div className="library-table-scroll" role="region" aria-label="Saved titles table, scroll horizontally for all columns" tabIndex={0}>
      <table className="library-table"><caption>{collection === "watch_later" ? "Watch Later" : "Not interested"} — {shown.length} saved titles</caption><thead><tr><th scope="col">Anime</th><th scope="col">Personal fit</th><th scope="col">MAL score / 10</th><th scope="col">Action</th></tr></thead><tbody>
        {shown.map(model => <tr key={model.mal_id}><th scope="row"><button className="table-title" onClick={() => onDetails(model)}><Poster title={model.display_title} url={model.cover_url} /><span>{model.display_title}</span></button></th><td>{personalFitText(model, feedEngineId)}</td><td>{model.mal_score === null ? "N/A" : model.mal_score.toFixed(2)}</td><td><button className="btn" disabled={pending} onClick={() => undo(model.mal_id!)}>{collection === "watch_later" ? "Remove from Watch Later" : "Show again"}</button></td></tr>)}
      </tbody></table>
    </div> : <div className={`library-shelf ${view}`}>
      {shown.map(model => <article className="library-card" key={model.mal_id}>
        <button className="poster-link" aria-label={`Details for ${model.display_title}`} onClick={() => onDetails(model)}><Poster title={model.display_title} url={model.cover_url} /></button>
        <div className="library-evidence"><h3><button onClick={() => onDetails(model)}>{model.display_title}</button></h3>
          <Genres genres={model.genres} />
          <dl className="library-scores"><div><dt>Personal fit</dt><dd>{personalFitText(model, feedEngineId)}</dd></div><div><dt>MAL score</dt><dd>{model.mal_score === null ? "N/A" : `${model.mal_score.toFixed(2)} / 10`}</dd></div></dl>
          <button className="btn" disabled={pending} onClick={() => undo(model.mal_id!)}>{collection === "watch_later" ? "Remove from Watch Later" : "Show again"}</button>
        </div>
      </article>)}
    </div>}
    {missing.length ? <section className="workspace-message"><h3>Saved decisions outside this feed</h3><p>Title details for these MyAnimeList IDs are absent from the available snapshots.</p>{missing.map(id => <p key={id}>MAL #{id} {profileId ? <button className="btn" disabled={resolving !== null} onClick={() => void resolve(id)}>{resolving === id ? "Loading…" : "Load details from MAL"}</button> : null} <button className="btn" disabled={pending} onClick={() => undo(id)}>{collection === "watch_later" ? "Remove saved decision" : "Show again"}</button></p>)}</section> : null}
  </>;
}
