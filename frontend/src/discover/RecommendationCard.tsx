/**
 * One recommendation.
 *
 * The Qt equivalent is recommendation_card.py: 1,125 lines, two paintEvent
 * overrides, two QLabel subclasses for text truncation, a cover memory cache
 * and a fixed CARD_WIDTH the grid arithmetic depends on. None of those have
 * an equivalent here, which is the measurement the decision gate is for.
 *
 * Artwork is loaded by the browser straight from MyAnimeList's CDN. The whole
 * of CoverImageService - validation, size bounds, magic-byte checks,
 * content-addressed disk cache, the aux-cover plumbing in MainWindow - is
 * replaced by an <img> and the HTTP cache. The validation still matters on a
 * server-side path, and a deployed web build should proxy these rather than
 * hotlink; for a local proof of concept the direct fetch is honest about what
 * the browser is actually doing.
 */

import { memo } from "react";
import type { RecommendationViewModel } from "../api/types";
import { usePlatform } from "../platform/PlatformContext";
import { Breakdown, ScoreRail } from "./ScoreRail";

interface Props {
  model: RecommendationViewModel;
  index: number;
  liked: boolean;
  disliked: boolean;
  watchLater: boolean;
  hidden: boolean;
  showBreakdown: boolean;
  onVote: (malId: number, action: "sentiment" | "watch_later" | "hidden", value: boolean) => void;
}

function RecommendationCardInner({
  model,
  index,
  liked,
  disliked,
  watchLater,
  hidden,
  showBreakdown,
  onVote,
}: Props) {
  const platform = usePlatform();
  const malId = model.mal_id;
  const meta = [model.year_text, model.episodes_text, model.status].filter(
    (item) => item && !item.toLocaleLowerCase().includes("not available"),
  );

  // Still a real anchor - it keeps the href in the status bar, middle-click,
  // and "copy link address". The handler exists because a bare target=_blank
  // inside the desktop webview would navigate the application window to
  // MyAnimeList, which has no chrome to come back from.
  const openMal = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (!model.mal_url) return;
    event.preventDefault();
    void platform.openExternal(model.mal_url);
  };

  return (
    <article
      className="card"
      data-hidden={hidden ? "true" : "false"}
      // Stagger, capped so a large feed does not make the last card wait.
      style={{ animationDelay: `${Math.min(index, 11) * 0.035}s` }}
    >
      <div className="card-art">
        <div className="placeholder" aria-hidden="true">
          No artwork
        </div>
        {model.cover_url ? (
          <img
            src={model.cover_url}
            alt=""
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
          />
        ) : null}
        {model.rank !== null ? <div className="card-rank">#{model.rank}</div> : null}
      </div>

      <div className="card-body">
        <h3 className="card-title" title={model.display_title}>
          {model.mal_url ? (
            <a
              href={model.mal_url}
              target="_blank"
              rel="noreferrer noopener"
              onClick={openMal}
            >
              {model.display_title}
            </a>
          ) : (
            model.display_title
          )}
        </h3>
        {model.secondary_title ? (
          <div className="card-secondary">{model.secondary_title}</div>
        ) : null}

        <div className="card-figures">
          <div className="card-match" data-available={String(model.personal_match_available)}>
            {model.personal_match_available ? model.personal_match.toFixed(1) : "--"}
            <i>%</i>
          </div>
          <div className="card-mal">
            <div className="lbl">MAL</div>
            {model.mal_score === null ? "not rated" : model.mal_score.toFixed(2)}
          </div>
        </div>

        <ScoreRail
          contributions={model.genre_contributions}
          score={model.personal_match}
          available={model.personal_match_available}
        />

        <div className="card-meta">
          {meta.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>

        {model.studios.length > 0 ? (
          <div className="card-meta">
            <span className="lbl">{model.studios.join(" · ")}</span>
          </div>
        ) : null}

        <p className="card-reason">{model.reason}</p>

        {showBreakdown ? (
          <Breakdown contributions={model.genre_contributions} score={model.personal_match} />
        ) : null}
      </div>

      <div className="card-actions">
        <button
          type="button"
          data-action="like"
          aria-pressed={liked}
          disabled={malId === null}
          onClick={() => malId !== null && onVote(malId, "sentiment", !liked)}
        >
          {liked ? "Liked" : "Like"}
        </button>
        <button
          type="button"
          data-action="later"
          aria-pressed={watchLater}
          disabled={malId === null}
          onClick={() => malId !== null && onVote(malId, "watch_later", !watchLater)}
        >
          Later
        </button>
        <button
          type="button"
          data-action="hide"
          aria-pressed={hidden || disliked}
          disabled={malId === null}
          onClick={() => malId !== null && onVote(malId, "hidden", !hidden)}
        >
          Not for me
        </button>
      </div>
    </article>
  );
}

// The feed re-renders on every filter keystroke and every vote. Without this,
// each keystroke re-renders every card; with it, only the cards whose props
// actually changed. The equivalent in Qt is not needing to think about it,
// because widgets are retained - this is a real cost React introduces, and it
// is one line.
export const RecommendationCard = memo(RecommendationCardInner);
