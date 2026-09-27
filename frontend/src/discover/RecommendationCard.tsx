/**
 * One recommendation, preserving the desktop card's poster and evidence roles.
 *
 * Order, top to bottom: poster, rank/MAL readings, preferred title, release
 * metadata, decisions, linked studio and genre tags, then the labelled
 * breakdown and database links. The API's reason belongs in the inspector.
 * Nothing is drawn over the artwork: the
 * desktop retired its match plate with the percentage (D-008), so the poster
 * is only the poster.
 *
 * The verdict row is exactly the two judgements a card can support before the
 * anime is watched (D-015, the desktop's CHANGE [NO-VERDICTS]): keep it for
 * later, or stop offering it. Both carry a short visible label and their state
 * in the accessible name and the glyph's filled variant, not in colour alone.
 */

import { memo, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import type { RecommendationViewModel } from "../api/types";
import { Icon } from "../assets/Icon";
import { usePlatform } from "../platform/PlatformContext";
import { fitRankText } from "./ScoreRail";
import { preferredTitle, useTitleLanguage } from "./titlePreference";
import { ExternalLinks, MetadataChips } from "./MetadataLinks";


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
type Artwork = Pick<RecommendationViewModel, "display_title" | "secondary_title" | "cover_url" | "large_cover_url">;

export function PosterArt({ model, large = false }: { model: Artwork; large?: boolean }) {
  const [failed, setFailed] = useState<string | null>(null);
  const title = preferredTitle(model, useTitleLanguage());
  const url = large ? model.large_cover_url || model.cover_url : model.cover_url;
  return <>
    <span className="placeholder" aria-hidden="true"><b>{initials(title)}</b><span>No artwork</span></span>
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
  return model.mal_score === null ? "MAL score unavailable" : `MAL score: ${model.mal_score.toFixed(2)} / 10`;
}

function cardMetadata(model: Pick<RecommendationViewModel, "year" | "media_type" | "episodes" | "status">) {
  const format = model.media_type?.trim().replaceAll("_", " ").toUpperCase() || null;
  const isMovie = format === "MOVIE";
  const facts = [model.year === null ? null : String(model.year), format, !isMovie && model.episodes !== null ? `${model.episodes} eps` : null].filter(Boolean);
  const status = model.status?.trim();
  const statusText = status === "Finished Airing" ? "Finished" : status === "Currently Airing" ? "Airing" : status;
  return { facts: facts.length ? facts.join(" · ") : "Release details unavailable", status: statusText && !/^not available$/i.test(statusText) ? statusText : "Status unavailable" };
}

function useFittedTitle(title: string) {
  const ref = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => {
    const heading = ref.current;
    if (!heading) return;
    heading.dataset.size = "large";
    heading.dataset.clipped = "false";
    // Short titles already fit the two-line reservation at the minimum card
    // width; avoid four forced layout reads for every card in a large feed.
    if ([...title].length <= 12) return;
    const text = heading.querySelector<HTMLElement>(".card-title-text");
    if (!text) return;
    const fit = () => {
      // Measure the complete, wrapping title. Clamping either the heading
      // or its button hides overflow from this measurement in Chromium.
      // The text span also excludes the button's 44px touch-target minimum.
      heading.dataset.clipped = "false";
      for (const size of ["large", "medium", "small", "minimum", "compact"]) {
        heading.dataset.size = size;
        if (text.scrollHeight <= heading.clientHeight + 1) break;
      }
      // Keep every lower card row in place. Only exceptionally long titles
      // that exceed the smallest existing type size need a final ellipsis;
      // the button's full accessible name, tooltip and Inspector remain.
      const lineHeight = Number.parseFloat(getComputedStyle(text).lineHeight);
      heading.style.setProperty("--title-lines", String(Math.max(1, Math.floor((heading.clientHeight + 1) / lineHeight))));
      heading.dataset.clipped = String(text.scrollHeight > heading.clientHeight + 1);
    };
    fit();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(fit);
    observer?.observe(heading);
    void document.fonts?.ready.then(fit);
    return () => observer?.disconnect();
  }, [title]);
  return ref;
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
  const title = preferredTitle(model, useTitleLanguage());
  if (!model.mal_url) return null;
  return <a className={className} href={model.mal_url} target="_blank" rel="noreferrer noopener"
    aria-label={label ?? `Open ${title} on MyAnimeList (external)`} title="Open on MyAnimeList"
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
  const title = preferredTitle(model, useTitleLanguage());
  const titleRef = useFittedTitle(title);
  const meta = cardMetadata(model);
  const rankAvailable = model.fit_rank != null && model.fit_pool_size != null;
  const labels = verdictLabels(watchLater, hidden);
  const locked = malId === null || pending || !!disabledReason;

  return (
    <article className="card" data-activity-mal-id={trackActivity ? malId ?? undefined : undefined}
      data-card-id={malId ?? undefined} data-hidden={hidden} aria-label={title}>
      <button type="button" className="card-art" aria-label={`Inspect ${title}`} onClick={() => onDetails(model)}>
        <PosterArt model={model} />
      </button>
      <div className="card-stats">
        <span className="card-fit" data-available={rankAvailable} title={fitRankText(model)}>
          {rankAvailable ? `PERSONAL #${model.fit_rank!.toLocaleString("en-US")}` : "Personal unavailable"}
        </span>
        <span className="card-mal" title={malScoreText(model)}>{model.mal_score === null ? "MAL unavailable" : `MAL ${model.mal_score.toFixed(2)}`}</span>
      </div>
      <h2 className="card-title" ref={titleRef}><button type="button" title={title} onClick={() => onDetails(model)}><span className="card-title-text">{title}</span></button></h2>
      <div className="card-meta"><span>{meta.facts}</span><span>{meta.status}</span></div>

      <div className="card-verdicts" role="group" aria-label={`Decisions for ${title}`}>
        <button type="button" className="verdict" data-action="later" aria-pressed={watchLater} aria-label={labels.later}
          title={disabledReason ?? (watchLater ? "Remove from Watch Later" : "Save to Watch Later")} disabled={locked}
          onClick={() => malId !== null && onVote(malId, "watch_later", !watchLater, model)}>
          <Icon name={watchLater ? "watch-later-active" : "watch-later"} /><span>{watchLater ? "Saved" : "Later"}</span>
        </button>
        <button type="button" className="verdict" data-action="hide" aria-pressed={hidden} aria-label={labels.hide}
          title={disabledReason ?? labels.hideTip} disabled={locked}
          onClick={() => malId !== null && onVote(malId, "hidden", !hidden, model)}>
          <Icon name={hidden ? "not-interested-active" : "not-interested"} /><span>{hidden ? "Show" : "Hide"}</span>
        </button>
      </div>

      <MetadataChips model={model} compact />
      <div className="card-utilities">
        <button type="button" className="breakdown-action" aria-label={`Open details for ${title}`}
          onClick={() => onDetails(model)}><Icon name="details-inspector" />Open details</button>
        <ExternalLinks model={model} onExternal={onExternal} />
      </div>
    </article>
  );
}

export const RecommendationCard = memo(RecommendationCardInner);
