/**
 * One recommendation, as `gui/recommendation_card.py` builds it.
 *
 * Order, top to bottom: poster, personal-fit line, title, secondary title,
 * the verdict row, studio and genre tags, year/status/episodes, MAL score, the
 * API's reason, and the utility row. Nothing is drawn over the artwork: the
 * desktop retired its match plate with the percentage (D-008), so the poster
 * is only the poster.
 *
 * The verdict row is exactly the two judgements a card can support before the
 * anime is watched (D-015, the desktop's CHANGE [NO-VERDICTS]): keep it for
 * later, or stop offering it. Both are icon toggles whose state is in the
 * accessible name and the glyph's filled variant, not in colour alone.
 */

import { memo, useState, type ReactNode } from "react";
import type { RecommendationViewModel } from "../api/types";
import { Icon } from "../assets/Icon";
import { usePlatform } from "../platform/PlatformContext";
import { fitRankText } from "./ScoreRail";


const CARD_TAG_SLOTS = 5;
export type Decision = "watch_later" | "hidden";

interface Props {
  model: RecommendationViewModel;
  watchLater: boolean;
  hidden: boolean;
  pending: boolean;
  /** Why the verdicts are unavailable, when they are. */
  disabledReason?: string;
  /** Mark the card as an activity-attributable feed position. */
  trackActivity?: boolean;
  onDetails: (model: RecommendationViewModel) => void;
  onExternal?: (model: RecommendationViewModel) => void;
  onVote: (malId: number, action: Decision, value: boolean, model?: RecommendationViewModel) => void;
}

export function initials(title: string): string {
  return title.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join("").toLocaleUpperCase();
}

/** A title's own initials on the poster's frame, never a stand-in cover. */
type Artwork = Pick<RecommendationViewModel, "display_title" | "cover_url" | "large_cover_url">;

export function PosterArt({ model, large = false }: { model: Artwork; large?: boolean }) {
  const [failed, setFailed] = useState<string | null>(null);
  const url = large ? model.large_cover_url || model.cover_url : model.cover_url;
  return <>
    <span className="placeholder" aria-hidden="true"><b>{initials(model.display_title)}</b><span>No artwork</span></span>
    {url && failed !== url ? (
      <img src={url} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setFailed(url)} />
    ) : null}
  </>;
}

export function verdictLabels(watchLater: boolean, hidden: boolean) {
  return {
    later: watchLater ? "Remove from Watch Later" : "Save for later",
    hide: hidden ? "Show this recommendation again" : "Not interested",
    hideTip: hidden ? "Show this anime in For You again." : "Stop recommending this anime. It stays in Not interested.",
  };
}

/** Only the parts that exist are shown; "not available" is left out, as the desktop row does. */
export function metaLine(model: Pick<RecommendationViewModel, "year_text" | "status" | "episodes_text">): string {
  return [model.year_text, model.status, model.episodes_text]
    .filter((item) => item && !item.toLocaleLowerCase().includes("not available"))
    .join(" · ");
}

export function malScoreText(model: Pick<RecommendationViewModel, "mal_score">): string {
  return `MAL score: ${model.mal_score === null ? "not rated" : `${model.mal_score.toFixed(2)} / 10`}`;
}

export function MalLink({ model, onExternal, className = "pill mal-link", label, children }: {
  model: RecommendationViewModel;
  /** Must contain any visible text the link carries (WCAG 2.5.3). */
  label?: string;
  onExternal?: (model: RecommendationViewModel) => void;
  className?: string;
  children?: ReactNode;
}) {
  const platform = usePlatform();
  if (!model.mal_url) return null;
  return <a className={className} href={model.mal_url} target="_blank" rel="noreferrer noopener"
    aria-label={label ?? `Open ${model.display_title} on MyAnimeList (external)`} title="Open on MyAnimeList"
    onClick={(event) => {
      // Preserve modified clicks and the real href in the browser.
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      void platform.openExternal(model.mal_url!).then(() => onExternal?.(model)).catch(() => {});
    }}>{children ?? <>MyAnimeList <span aria-hidden="true">↗</span></>}</a>;
}

function RecommendationCardInner({
  model, watchLater, hidden, pending, disabledReason, trackActivity = false, onDetails, onVote, onExternal,
}: Props) {
  const malId = model.mal_id;
  const labels = verdictLabels(watchLater, hidden);
  const locked = malId === null || pending || !!disabledReason;
  const studio = model.studios[0];
  // Five slots fill the three-row reservation even with long names; when
  // the tags do not fit, the last slot becomes the "+n" that names the rest.
  const available = CARD_TAG_SLOTS - (studio ? 1 : 0);
  const overflowing = model.studios.length > 1 || model.genres.length > available;
  const shownGenres = Math.min(model.genres.length, overflowing ? available - 1 : available);
  const moreTags = [...model.studios.slice(1), ...model.genres.slice(shownGenres)];
  const meta = metaLine(model);

  return (
    <article className="card" data-activity-mal-id={trackActivity ? malId ?? undefined : undefined}
      data-card-id={malId ?? undefined} data-hidden={hidden} aria-label={model.display_title}>
      <button type="button" className="card-art" aria-label={`Inspect ${model.display_title}`} onClick={() => onDetails(model)}>
        <PosterArt model={model} />
      </button>
      <p className="card-fit" data-available={model.fit_rank != null && model.fit_pool_size != null}>{fitRankText(model)}</p>
      <h2 className="card-title"><button type="button" title={model.display_title} onClick={() => onDetails(model)}>{model.display_title}</button></h2>
      <div className="card-secondary" title={model.secondary_title ?? undefined}>{model.secondary_title || " "}</div>

      <div className="card-verdicts" role="group" aria-label={`Decisions for ${model.display_title}`}>
        <button type="button" className="verdict" data-action="later" aria-pressed={watchLater} aria-label={labels.later}
          title={disabledReason ?? labels.later} disabled={locked}
          onClick={() => malId !== null && onVote(malId, "watch_later", !watchLater, model)}>
          <Icon name={watchLater ? "watch-later-active" : "watch-later"} />
        </button>
        <button type="button" className="verdict" data-action="hide" aria-pressed={hidden} aria-label={labels.hide}
          title={disabledReason ?? labels.hideTip} disabled={locked}
          onClick={() => malId !== null && onVote(malId, "hidden", !hidden, model)}>
          <Icon name={hidden ? "not-interested-active" : "not-interested"} />
        </button>
      </div>

      {/* gui/metadata_tags.py: the tags keep a fixed-height reservation, and
          anything past it collapses into one "+n" naming the rest, so a card
          never hides a genre without saying so. */}
      <div className="card-tags" title={[...model.studios, ...model.genres].join(" · ")}>
        {studio ? <span className="card-tag studio"><span className="visually-hidden">Studio: </span>{studio}</span> : null}
        {model.genres.slice(0, shownGenres).map((genre) => <span className="card-tag" key={genre}><span className="visually-hidden">Genre: </span>{genre}</span>)}
        {moreTags.length ? <span className="card-tag more" title={moreTags.join(" · ")}>
          +{moreTags.length}<span className="visually-hidden"> more: {moreTags.join(", ")}</span>
        </span> : null}
      </div>
      <div className="card-meta">{meta}</div>
      <div className="card-mal">{malScoreText(model)}</div>
      <p className="card-reason" title={model.reason || undefined}>{model.reason?.trim() ? model.reason : null}</p>
      <div className="card-utilities">
        <button type="button" className="icon-action" aria-label={`Open the full breakdown for ${model.display_title}`} title="Open the full breakdown"
          onClick={() => onDetails(model)}><Icon name="details-inspector" /></button>
        <MalLink model={model} onExternal={onExternal} className="icon-action"><Icon name="external-mal" /></MalLink>
      </div>
    </article>
  );
}

export const RecommendationCard = memo(RecommendationCardInner);
