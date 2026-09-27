/**
 * The Score Inspector, as `gui/recommendation_detail_dialog.py` lays it out.
 *
 * A rack headed "ANIREC / SCORE INSPECTOR" with previous/next across the
 * visible feed and Close. The media column holds the 2:3 poster, optional PV,
 * and sourced database links. Identity, metadata, and synopsis precede the
 * PERSONAL FIT panel and the two decisions.
 *
 * PERSONAL FIT shows the persisted personal rank and answering engine.
 * Legacy explanation payloads are not displayed or fetched.
 *
 * A native modal <dialog> supplies focus containment and Escape. On close,
 * focus goes back to the card of the title being inspected, which after
 * previous/next is not necessarily the control that opened it.
 */

import { useEffect, useId, useRef, useState } from "react";
import type { RecommendationViewModel } from "../api/types";
import { preferredTitle, useTitleLanguage } from "./titlePreference";
import { Icon } from "../assets/Icon";
import { PosterArt, type Decision } from "./RecommendationCard";
import { fitRankText, rankingEngineLabel } from "./ScoreRail";
import { ExternalLinks, MetadataChips, pvEmbedUrl, pvThumbnailUrl } from "./MetadataLinks";

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
  onVote: (malId: number, action: Decision, value: boolean, model?: RecommendationViewModel) => void;
  onExternal?: (model: RecommendationViewModel) => void;
}

const two = (value: number) => String(value).padStart(2, "0");

function PvPreview({ thumbnail, title, onPlay }: { thumbnail: string; title: string; onPlay: () => void }) {
  const [failed, setFailed] = useState(false);
  return <button type="button" className="pv-entry" aria-label={`Play PV for ${title}`} onClick={onPlay}>
    <span className="pv-preview-image">
      {!failed ? <img src={thumbnail} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} /> : null}
      <span className="pv-preview-play" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 6 19 12 9 18Z" /></svg>
      </span>
      {failed ? <span className="pv-preview-fallback">PV preview unavailable</span> : null}
    </span>
    <span className="pv-preview-caption"><span>Play PV</span><span>YouTube</span></span>
  </button>;
}

export function ScoreInspector({
  model, position, total, engineId, watchLater, hidden, pending, disabledReason,
  onPrevious, onNext, onClose, onVote, onExternal,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const videoDialog = useRef<HTMLDialogElement>(null);
  const title = preferredTitle(model, useTitleLanguage());
  const headingId = useId();
  const synopsisId = useId();
  const [synopsis, setSynopsis] = useState(false);
  const [videoOpen, setVideoOpen] = useState(false);
  const current = useRef(model.mal_id);
  current.current = model.mal_id;

  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    return () => node.close();
  }, []);
  // A new title starts folded, as set_model resets the toggle.
  useEffect(() => { setSynopsis(false); setVideoOpen(false); }, [model.mal_id]);
  useEffect(() => {
    if (videoOpen) videoDialog.current?.showModal();
    return () => { if (videoDialog.current?.open) videoDialog.current.close(); };
  }, [videoOpen]);

  const closeAndReturn = () => {
    onClose();
    // After the dialog has gone, return focus to the card being inspected.
    requestAnimationFrame(() => {
      // Discover and Library both stay mounted; only a visible copy of the
      // card can take focus.
      const id = current.current;
      const target = id === null ? undefined
        : [...document.querySelectorAll<HTMLElement>(`[data-card-id="${id}"] .card-title button, [data-card-id="${id}"] .row-title button, [data-card-id="${id}"] .table-title`)]
          .find((node) => !node.closest("[hidden]"));
      // The title may have no visible card any more: stepped to another page,
      // or just marked Not interested. Then the list itself takes focus, not
      // the page body.
      const fallback = [...document.querySelectorAll<HTMLElement>("[data-inspector-return]")]
        .find((node) => !node.closest("[hidden]"));
      (target ?? fallback)?.focus();
    });
  };

  const malId = model.mal_id;
  const locked = malId === null || pending || !!disabledReason;
  const navigable = total > 1;
  const videoUrl = pvEmbedUrl(model);
  const videoThumbnail = pvThumbnailUrl(model);
  const synopsisText = model.synopsis?.trim() || "";
  const synopsisLong = synopsisText.length > 360;
  const synopsisPreview = synopsisLong ? `${synopsisText.slice(0, 360).replace(/\s+\S*$/, "")}…` : synopsisText;
  const facts: [string, string | null][] = [
    ["MAL score", model.mal_score === null ? "Unavailable" : `${model.mal_score.toFixed(2)} / 10`],
    ["Type", model.media_type],
    ["Episodes", model.episodes_text],
    ["Status", model.status],
    ["Airing year", model.year_text],
    ["Aired", model.aired_text],
  ];

  return <dialog ref={dialog} className="inspector" aria-labelledby={headingId}
    onClick={(event) => {
      if (event.target !== event.currentTarget) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right
          || event.clientY < bounds.top || event.clientY > bounds.bottom) {
        event.currentTarget.close();
      }
    }}
    onKeyDown={(event) => {
      const target = event.target as HTMLElement;
      if (target.closest("summary, input, textarea, select, .pv-lightbox")) return;
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
        <div className="inspector-media">
          <div className="inspector-poster"><PosterArt key={model.mal_id ?? model.display_title} model={model} large /></div>
          {videoUrl && videoThumbnail ? <PvPreview key={videoUrl} thumbnail={videoThumbnail} title={title} onPlay={() => setVideoOpen(true)} /> : null}
          <ExternalLinks model={model} onExternal={onExternal} labelled />
        </div>
        <div className="inspector-column">
          <h2 id={headingId}>{title}</h2>
          {model.alternative_titles.length ? <p className="inspector-alternatives">Alternative titles: {model.alternative_titles.join(" · ")}</p> : null}
          <dl className="inspector-facts">
            {facts.filter(([, value]) => value !== null).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
          <div className="inspector-metadata">
            {model.studios.length ? <div><span className="lbl">STUDIO</span><MetadataChips model={{ ...model, genres: [] }} onNavigate={() => dialog.current?.close()} /></div> : null}
            {model.genres.length ? <div><span className="lbl">GENRES</span><MetadataChips model={{ ...model, studios: [] }} onNavigate={() => dialog.current?.close()} /></div> : null}
          </div>
          <section className="synopsis-panel" aria-label="Synopsis">
            <h3 className="lbl">SYNOPSIS</h3>
            <p id={synopsisId} className="synopsis">{synopsisText ? synopsis && synopsisLong ? synopsisText : synopsisPreview : "No synopsis available."}</p>
            {synopsisLong ? <button type="button" className="synopsis-toggle" aria-expanded={synopsis} aria-controls={synopsisId}
              onClick={() => setSynopsis((open) => !open)}>{synopsis ? "Read less" : "Read more"}</button> : null}
          </section>

          <section className="fit-panel" aria-labelledby={`${headingId}-fit`}>
            <header>
              <h3 id={`${headingId}-fit`}>PERSONAL FIT</h3>
              <span className="fit-mode">RANKED RESULT</span>
            </header>
            <div className="fit-readout">
              <strong>{fitRankText(model)}</strong>
              {model.fit_rank != null ? <span className="fit-engine">Ranked by the {rankingEngineLabel(engineId)}</span> : null}
            </div>
          </section>

          <div className="inspector-actions">
            <button type="button" className="btn" data-action="later" aria-pressed={watchLater} disabled={locked} title={disabledReason}
              onClick={() => malId !== null && onVote(malId, "watch_later", !watchLater, model)}>{watchLater ? "Remove saved" : "Watch Later"}</button>
            <button type="button" className="btn" data-action="hide" aria-pressed={hidden} disabled={locked} title={disabledReason}
              onClick={() => malId !== null && onVote(malId, "hidden", !hidden, model)}>{hidden ? "Show again" : "Not interested"}</button>
          </div>
        </div>
      </div>

    </div>
    {videoOpen && videoUrl ? <dialog ref={videoDialog} className="pv-lightbox" aria-label={`PV for ${title}`}
      onClose={() => setVideoOpen(false)} onClick={(event) => { if (event.target === event.currentTarget) event.currentTarget.close(); }}>
      <div className="pv-lightbox-content">
        <button type="button" className="btn" autoFocus onClick={() => videoDialog.current?.close()}>Close PV</button>
        <iframe title={`PV for ${title}`} src={videoUrl} allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowFullScreen referrerPolicy="strict-origin-when-cross-origin" />
      </div>
    </dialog> : null}
  </dialog>;
}
