import { memo, useState } from "react";
import type { RecommendationViewModel } from "../api/types";
import { FitIndicator } from "./ScoreRail";
import { MalLink } from "./RecommendationDetails";

export type Sentiment = "liked" | "disliked" | null;

interface Props {
  model: RecommendationViewModel;
  rankingEngineId: string | null;
  watchLater: boolean;
  hidden: boolean;
  sentiment: Sentiment;
  pending: boolean;
  sentimentPending: boolean;
  onDetails: (model: RecommendationViewModel) => void;
  onExternal?: (model: RecommendationViewModel) => void;
  onVote: (malId: number, action: "watch_later" | "hidden", value: boolean) => void;
  onSentiment: (malId: number, sentiment: Sentiment) => void;
}

function RecommendationCardInner({
  model,
  rankingEngineId,
  watchLater,
  hidden,
  sentiment,
  pending,
  sentimentPending,
  onDetails,
  onVote,
  onSentiment,
  onExternal,
}: Props) {
  const [failedCover, setFailedCover] = useState<string | null>(null);
  const malId = model.mal_id;
  const meta = [model.year_text, model.episodes_text, model.status].filter(
    (item) => item && !item.toLocaleLowerCase().includes("not available"),
  );
  const initials = model.display_title.split(/\s+/).slice(0, 2).map((word) => word[0]).join("");
  const sentimentDisabled = malId === null || pending || sentimentPending;

  return (
    <article className="card" data-activity-mal-id={malId ?? undefined} data-hidden={hidden} aria-label={model.display_title}>
      <div className="card-art">
        <button type="button" className="card-art-open" aria-label={`Inspect ${model.display_title}`} onClick={() => onDetails(model)}>
          <span className="placeholder" aria-hidden="true"><b>{initials}</b><span>No artwork</span></span>
          {model.cover_url && failedCover !== model.cover_url ? (
            <img src={model.cover_url} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer"
              onError={() => setFailedCover(model.cover_url)} />
          ) : null}
        </button>
        {model.rank !== null ? <span className="card-rank" aria-label={`Feed position ${model.rank}`}>#{model.rank}</span> : null}
        <FitIndicator model={model} engineId={rankingEngineId} onOpen={() => onDetails(model)} />
      </div>

      <div className="card-body">
        <h2 className="card-title"><button type="button" title={model.display_title} onClick={() => onDetails(model)}>{model.display_title}</button></h2>
        <div className="card-secondary" title={model.secondary_title ?? undefined}>{model.secondary_title || "\u00a0"}</div>

        <div className="card-sentiment" role="group" aria-label={`Your reaction to ${model.display_title}`}>
          <button type="button" data-action="like" aria-pressed={sentiment === "liked"} disabled={sentimentDisabled}
            onClick={() => malId !== null && onSentiment(malId, sentiment === "liked" ? null : "liked")}>Like</button>
          <button type="button" data-action="dislike" aria-pressed={sentiment === "disliked"} disabled={sentimentDisabled}
            onClick={() => malId !== null && onSentiment(malId, sentiment === "disliked" ? null : "disliked")}>Dislike</button>
        </div>
        <p className="card-sentiment-note">Saved for evaluation only; votes do not change recommendations yet.</p>

        <div className="card-actions" aria-label={`Decisions for ${model.display_title}`}>
          <button type="button" data-action="later" aria-pressed={watchLater} disabled={malId === null || pending}
            onClick={() => malId !== null && onVote(malId, "watch_later", !watchLater)}>
            {watchLater ? "Saved for later" : "Save for later"}
          </button>
          <button type="button" data-action="hide" aria-pressed={hidden} disabled={malId === null || pending}
            onClick={() => malId !== null && onVote(malId, "hidden", !hidden)}>
            {hidden ? "Show again" : "Set aside"}
          </button>
        </div>
        {hidden ? <p className="card-set-aside">Set aside. Excluded from future feeds.</p> : null}

        <div className="card-tags" title={[...model.studios, ...model.genres].join(" · ")}>
          {model.studios.map((studio) => <span className="card-tag studio" key={`s-${studio}`}>{studio}</span>)}
          {model.genres.map((genre) => <span className="card-tag" key={`g-${genre}`}>{genre}</span>)}
        </div>
        <div className="card-meta">{meta.map((item) => <span key={item}>{item}</span>)}</div>
        <div className="card-mal">MAL score: {model.mal_score === null ? "not rated" : `${model.mal_score.toFixed(2)} / 10`}</div>
        <div className="card-utilities">
          <button type="button" className="pill" onClick={() => onDetails(model)}>Details</button>
          <MalLink model={model} onExternal={onExternal} />
        </div>
      </div>
    </article>
  );
}

export const RecommendationCard = memo(RecommendationCardInner);
