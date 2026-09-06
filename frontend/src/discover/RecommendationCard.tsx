/** Discover decisions follow PySide: save a prospect or set it aside, not rate it. */
import { memo, useState } from "react";
import type { RecommendationViewModel } from "../api/types";
import { Breakdown, ScoreRail } from "./ScoreRail";
import { MalLink } from "./RecommendationDetails";

interface Props {
  model: RecommendationViewModel;
  watchLater: boolean;
  hidden: boolean;
  showBreakdown: boolean;
  pending: boolean;
  onDetails: (model: RecommendationViewModel) => void;
  onVote: (malId: number, action: "watch_later" | "hidden", value: boolean) => void;
}

function RecommendationCardInner({ model, watchLater, hidden, showBreakdown, pending, onDetails, onVote }: Props) {
  const [failedCover, setFailedCover] = useState<string | null>(null);
  const malId = model.mal_id;
  const meta = [model.year_text, model.episodes_text, model.status].filter(
    (item) => item && !item.toLocaleLowerCase().includes("not available"),
  );
  const initials = model.display_title.split(/\s+/).slice(0, 2).map((word) => word[0]).join("");

  return (
    <article className="card" data-hidden={hidden} aria-label={model.display_title}>
      <button type="button" className="card-art" aria-label={`Inspect ${model.display_title}`} onClick={() => onDetails(model)}>
        <span className="placeholder" aria-hidden="true"><b>{initials}</b><span>No artwork</span></span>
        {model.cover_url && failedCover !== model.cover_url ? (
          <img src={model.cover_url} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer"
            onError={() => setFailedCover(model.cover_url)} />
        ) : null}
        {model.rank !== null ? <span className="card-rank">#{model.rank}</span> : null}
        <span className="card-scoreplate">
          <span className="card-figures">
            <span className="lbl">Personal match</span>
            <span className="card-match" data-available={model.personal_match_available}>
              {model.personal_match_available ? <>{model.personal_match.toFixed(1)}<i>%</i></> : "—"}
            </span>
          </span>
          <ScoreRail contributions={model.genre_contributions} score={model.personal_match} available={model.personal_match_available} />
        </span>
      </button>

      <div className="card-body">
        <h2 className="card-title"><button type="button" title={model.display_title} onClick={() => onDetails(model)}>{model.display_title}</button></h2>
        <div className="card-secondary" title={model.secondary_title ?? undefined}>{model.secondary_title || "\u00a0"}</div>

        <div className="card-actions" aria-label={`Decisions for ${model.display_title}`}>
          <button type="button" data-action="later" aria-pressed={watchLater} disabled={malId === null || pending}
            onClick={() => malId !== null && onVote(malId, "watch_later", !watchLater)}>
            {watchLater ? "Saved for later" : "Save for later"}
          </button>
          <button type="button" data-action="hide" aria-pressed={hidden} disabled={malId === null || pending}
            onClick={() => malId !== null && onVote(malId, "hidden", !hidden)}>
            {hidden ? "Show again" : "Not interested"}
          </button>
        </div>
        {hidden ? <p className="card-set-aside">Set aside. Excluded from future feeds.</p> : null}

        <div className="card-tags" title={[...model.studios, ...model.genres].join(" · ")}>
          {model.studios.map((studio) => <span className="card-tag studio" key={`s-${studio}`}>{studio}</span>)}
          {model.genres.map((genre) => <span className="card-tag" key={`g-${genre}`}>{genre}</span>)}
        </div>
        <div className="card-meta">{meta.map((item) => <span key={item}>{item}</span>)}</div>
        <div className="card-mal">MAL score: {model.mal_score === null ? "not rated" : `${model.mal_score.toFixed(2)} / 10`}</div>
        <p className="card-reason">{model.reason}</p>
        {showBreakdown ? <Breakdown contributions={model.genre_contributions} score={model.personal_match} available={model.personal_match_available} /> : null}
        <div className="card-utilities">
          <button type="button" className="pill" onClick={() => onDetails(model)}>Details</button>
          <MalLink model={model} />
        </div>
      </div>
    </article>
  );
}

export const RecommendationCard = memo(RecommendationCardInner);
