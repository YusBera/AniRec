/**
 * The Score Inspector, as `gui/recommendation_detail_dialog.py` lays it out.
 *
 * A rack headed "ANIREC / SCORE INSPECTOR" with previous/next across the
 * visible feed and Close; a large 2:3 poster beside the title and a grid of
 * facts; the PERSONAL FIT panel; the two decisions as text buttons with
 * "Open on MyAnimeList"; and the synopsis folded behind "READ SYNOPSIS +".
 *
 * The PERSONAL FIT panel carries the honest `why` (DOMAIN_RULES,
 * "Explanation"): exact additive parts for the heuristic engine,
 * counterfactual removal for the sequence model, or a stated absence. The
 * desktop's contribution rail and "SUMS TO" row are gone with the percentage
 * they summed to, so nothing here is presented as shares of a score.
 *
 * A native modal <dialog> supplies focus containment and Escape. On close,
 * focus goes back to the card of the title being inspected, which after
 * previous/next is not necessarily the control that opened it.
 */

import { useEffect, useId, useRef, useState } from "react";
import type { RecommendationViewModel } from "../api/types";
import { Icon } from "../assets/Icon";
import { MalLink, PosterArt, type Decision } from "./RecommendationCard";
import { fitRankText, rankingEngineLabel, WhyExplanation } from "./ScoreRail";

interface Props {
  model: RecommendationViewModel;
  /** 1-based position in the visible feed, or null when the title has left it. */
  position: number | null;
  total: number;
  engineId: string | null;
  watchLater: boolean;
  hidden: boolean;
  pending: boolean;
  disabledReason?: string;
  onPrevious: () => void;
  onNext: () => void;
  onClose: () => void;
  onVote: (malId: number, action: Decision, value: boolean) => void;
  onExternal?: (model: RecommendationViewModel) => void;
}

const two = (value: number) => String(value).padStart(2, "0");

export function ScoreInspector({
  model, position, total, engineId, watchLater, hidden, pending, disabledReason,
  onPrevious, onNext, onClose, onVote, onExternal,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const headingId = useId();
  const synopsisId = useId();
  const [synopsis, setSynopsis] = useState(false);
  const current = useRef(model.mal_id);
  current.current = model.mal_id;

  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    return () => node.close();
  }, []);
  // A new title starts folded, as set_model resets the toggle.
  useEffect(() => setSynopsis(false), [model.mal_id]);

  const closeAndReturn = () => {
    onClose();
    // After the dialog has gone, return focus to the card being inspected.
    requestAnimationFrame(() => {
      const target = current.current === null ? null
        : document.querySelector<HTMLElement>(`[data-card-id="${current.current}"] .card-title button, [data-card-id="${current.current}"] .row-title button, [data-card-id="${current.current}"] .table-title`);
      target?.focus();
    });
  };

  const malId = model.mal_id;
  const locked = malId === null || pending || !!disabledReason;
  const navigable = total > 1;
  const facts: [string, string | null][] = [
    ["MAL score", model.mal_score === null ? "Not rated" : `${model.mal_score.toFixed(2)} / 10`],
    ["Episodes", model.episodes_text],
    ["Status", model.status],
    ["Airing year", model.year_text],
    ["Aired", model.aired_text],
    ["Studio", model.studios.join(" · ") || "Not available"],
    ["Genres", model.genres.join(" · ") || "Not available"],
  ];

  return <dialog ref={dialog} className="inspector" aria-labelledby={headingId}
    onKeyDown={(event) => {
      const target = event.target as HTMLElement;
      if (target.closest("summary, input, textarea, select")) return;
      if (event.key === "ArrowLeft" && navigable) { event.preventDefault(); onPrevious(); }
      if (event.key === "ArrowRight" && navigable) { event.preventDefault(); onNext(); }
    }}
    onClose={() => {
      // StrictMode reopens the same node after effect cleanup. Ignore the
      // queued close event from that rehearsal if it is already open again.
      if (!dialog.current?.open) closeAndReturn();
    }}>
    <header className="inspector-rack">
      <span className="inspector-legend">ANIREC <span aria-hidden="true">/</span> SCORE INSPECTOR</span>
      <nav className="inspector-nav" aria-label="Recommendations in this feed">
        <button type="button" className="inspector-step" aria-label="Inspect previous recommendation" disabled={!navigable} onClick={onPrevious}>
          <Icon name="chevron-left" />
        </button>
        <span className="inspector-position" aria-live="polite">
          <span className="visually-hidden">Recommendation </span>{position === null ? "--" : two(position)} / {two(total)}
        </span>
        <button type="button" className="inspector-step" aria-label="Inspect next recommendation" disabled={!navigable} onClick={onNext}>
          <Icon name="chevron-right" />
        </button>
      </nav>
      <button type="button" className="btn" autoFocus aria-label="Close score inspector" onClick={() => dialog.current?.close()}>Close</button>
    </header>

    <div className="inspector-body">
      <div className="inspector-hero">
        <div className="inspector-poster"><PosterArt key={model.mal_id ?? model.display_title} model={model} large /></div>
        <div className="inspector-column">
          <h2 id={headingId}>{model.display_title}</h2>
          {model.secondary_title ? <p className="inspector-secondary">{model.secondary_title}</p> : null}
          {model.alternative_titles.length ? <p className="inspector-alternatives">Alternative titles: {model.alternative_titles.join(" · ")}</p> : null}
          <dl className="inspector-facts">
            {facts.filter(([, value]) => value !== null).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>

          <section className="fit-panel" aria-labelledby={`${headingId}-fit`}>
            <header>
              <h3 id={`${headingId}-fit`}>PERSONAL FIT</h3>
              <span className="fit-mode">RANKED RESULT</span>
            </header>
            <div className="fit-readout">
              <strong>{fitRankText(model)}</strong>
              {model.fit_rank != null ? <span className="fit-engine">Ranked by the {rankingEngineLabel(engineId)}</span> : null}
              {model.reason?.trim() ? <p className="fit-reason">{model.reason}</p> : null}
            </div>
            <div className="fit-why">
              <h4>Why this pick</h4>
              <WhyExplanation why={model.why} />
            </div>
          </section>

          <div className="inspector-actions">
            <button type="button" className="btn" data-action="later" aria-pressed={watchLater} disabled={locked} title={disabledReason}
              onClick={() => malId !== null && onVote(malId, "watch_later", !watchLater)}>{watchLater ? "Remove saved" : "Watch Later"}</button>
            <button type="button" className="btn" data-action="hide" aria-pressed={hidden} disabled={locked} title={disabledReason}
              onClick={() => malId !== null && onVote(malId, "hidden", !hidden)}>{hidden ? "Show again" : "Not interested"}</button>
            <span className="spacer" />
            <MalLink model={model} onExternal={onExternal} className="inspector-mal">Open on MyAnimeList <span aria-hidden="true">↗</span></MalLink>
          </div>
        </div>
      </div>

      <section className="synopsis-panel">
        <button type="button" className="synopsis-toggle" aria-expanded={synopsis} aria-controls={synopsisId}
          onClick={() => setSynopsis((open) => !open)}>
          {synopsis ? "HIDE SYNOPSIS −" : "READ SYNOPSIS +"}
        </button>
        <p id={synopsisId} className="synopsis" hidden={!synopsis}>{model.synopsis || "No synopsis available."}</p>
      </section>
    </div>
  </dialog>;
}
