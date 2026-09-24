/**
 * Cards, List and Table: one query rendered three ways.
 *
 * Qt equivalent: `RecommendationExplorerPage` in `gui/recommendation_page.py`
 * (the view toggle and table) and `gui/recommendation_row.py` (the List row).
 * Discover and My Library use the same explorer there, and the same views
 * here. Every value in every view is a field the API returned; the List row's
 * facts line joins only the parts that exist, as `_facts_line` does.
 *
 * Artwork is 2:3 in all three, including the List and Table thumbnails.
 */

import type { RecommendationViewModel } from "../api/types";
import { Icon } from "../assets/Icon";
import { PosterArt, RecommendationCard, type Decision } from "./RecommendationCard";
import { fitRankText } from "./ScoreRail";

export type ViewMode = "cards" | "list" | "table";

const VIEWS: { mode: ViewMode; label: string; icon: "view-grid" | "view-list" | "view-table"; name: string }[] = [
  { mode: "cards", label: "Cards", icon: "view-grid", name: "Show recommendations as cards" },
  { mode: "list", label: "List", icon: "view-list", name: "Show recommendations as a compact list" },
  { mode: "table", label: "Table", icon: "view-table", name: "Show recommendations as a table" },
];

export function ViewToggle({ view, onChange }: { view: ViewMode; onChange: (view: ViewMode) => void }) {
  return <div className="view-toggle" role="group" aria-label="View">
    {VIEWS.map((option) => <button key={option.mode} type="button" className="view-button" aria-pressed={view === option.mode}
      title={option.name} onClick={() => onChange(option.mode)}>
      <Icon name={view === option.mode ? `${option.icon}-active` : option.icon} />{option.label}
    </button>)}
  </div>;
}

export interface FeedViewProps {
  view: ViewMode;
  models: RecommendationViewModel[];
  caption: string;
  watchLater: (malId: number | null) => boolean;
  hidden: (malId: number | null) => boolean;
  pending: boolean;
  disabledReason?: string;
  trackActivity?: boolean;
  onDetails: (model: RecommendationViewModel) => void;
  onExternal?: (model: RecommendationViewModel) => void;
  onVote: (malId: number, action: Decision, value: boolean) => void;
}

export function FeedView(props: FeedViewProps) {
  if (props.view === "list") return <ListView {...props} />;
  if (props.view === "table") return <TableView {...props} />;
  return <div className="feed">
    {props.models.map((model) => <RecommendationCard key={model.mal_id ?? model.display_title} model={model}
      watchLater={props.watchLater(model.mal_id)} hidden={props.hidden(model.mal_id)} pending={props.pending}
      disabledReason={props.disabledReason} trackActivity={props.trackActivity}
      onDetails={props.onDetails} onExternal={props.onExternal} onVote={props.onVote} />)}
  </div>;
}

/** `_facts_line`: studio, year, episodes and MAL score, only where known. */
export function factsLine(model: RecommendationViewModel): string {
  const parts: string[] = [];
  if (model.studios[0]) parts.push(model.studios[0]);
  if (model.year !== null) parts.push(String(model.year));
  if (model.episodes !== null) parts.push(model.episodes_text);
  if (model.mal_score !== null) parts.push(`MAL ${model.mal_score.toFixed(2)}`);
  return parts.join(" · ");
}

function Decisions({ model, props, compact = false }: { model: RecommendationViewModel; props: FeedViewProps; compact?: boolean }) {
  const malId = model.mal_id;
  const saved = props.watchLater(malId);
  const hidden = props.hidden(malId);
  const locked = malId === null || props.pending || !!props.disabledReason;
  return <>
    <button type="button" className={`btn row-action${compact ? " compact" : ""}`} data-action="later" aria-pressed={saved} disabled={locked}
      title={props.disabledReason} onClick={() => malId !== null && props.onVote(malId, "watch_later", !saved)}>
      {saved ? "Remove from Watch Later" : "Watch Later"}
    </button>
    <button type="button" className={`btn row-action${compact ? " compact" : ""}`} data-action="hide" aria-pressed={hidden} disabled={locked}
      title={props.disabledReason ?? (hidden ? "Show this anime in For You again." : "Stop recommending this anime. It stays in Not interested.")}
      onClick={() => malId !== null && props.onVote(malId, "hidden", !hidden)}>
      {hidden ? "Show again" : "Not interested"}
    </button>
  </>;
}

function ListView(props: FeedViewProps) {
  return <ul className="feed-list" aria-label={props.caption}>
    {props.models.map((model) => {
      const facts = factsLine(model);
      return <li key={model.mal_id ?? model.display_title} className="feed-row" data-card-id={model.mal_id ?? undefined}
        data-hidden={props.hidden(model.mal_id)}>
        <button type="button" className="row-art" aria-label={`Inspect ${model.display_title}`} onClick={() => props.onDetails(model)}>
          <PosterArt model={model} />
        </button>
        <div className="row-text">
          <h2 className="row-title"><button type="button" onClick={() => props.onDetails(model)}>{model.display_title}</button></h2>
          {facts ? <p className="row-facts">{facts}</p> : null}
          <p className="row-reason">{model.reason?.trim() || model.genres.join(" · ")}</p>
        </div>
        <div className="row-tags">
          <span className="row-fit">{fitRankText(model)}</span>
          {model.genres[0] ? <span className="row-genre">{model.genres[0]}</span> : null}
        </div>
        <div className="row-actions">
          <Decisions model={model} props={props} />
          <button type="button" className="btn row-action" onClick={() => props.onDetails(model)}
            aria-label={`Details for ${model.display_title}`}>Details</button>
        </div>
      </li>;
    })}
  </ul>;
}

function TableView(props: FeedViewProps) {
  return <div className="table-scroll" role="region" aria-label={`${props.caption} table, scroll horizontally for all columns`} tabIndex={0}>
    <table className="feed-table">
      <caption>{props.caption}</caption>
      <thead><tr>
        <th scope="col">Rank</th><th scope="col">Title</th><th scope="col">Personal match</th><th scope="col">MAL score</th>
        <th scope="col">Genres</th><th scope="col">Year</th><th scope="col">Status</th><th scope="col">Episodes</th><th scope="col">Actions</th>
      </tr></thead>
      <tbody>{props.models.map((model) => <tr key={model.mal_id ?? model.display_title} data-card-id={model.mal_id ?? undefined}
        data-hidden={props.hidden(model.mal_id)}>
        <td>{model.rank ?? "N/A"}</td>
        <th scope="row"><button type="button" className="table-title" onClick={() => props.onDetails(model)}>
          <span className="table-thumb" aria-hidden="true"><PosterArt model={model} /></span><span>{model.display_title}</span>
        </button></th>
        <td className="table-fit">{fitRankText(model)}</td>
        <td>{model.mal_score === null ? "Not rated" : model.mal_score.toFixed(2)}</td>
        <td>{model.genres.join(" · ") || "Not available"}</td>
        <td>{model.year ?? "Not available"}</td>
        <td>{model.status}</td>
        <td>{model.episodes ?? "Not available"}</td>
        <td><div className="table-actions"><Decisions model={model} props={props} compact /></div></td>
      </tr>)}</tbody>
    </table>
  </div>;
}
