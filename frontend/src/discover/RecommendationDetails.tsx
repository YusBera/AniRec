import { useEffect, useId, useRef } from "react";
import type { RecommendationViewModel } from "../api/types";
import { usePlatform } from "../platform/PlatformContext";
import { personalFitText, WhyExplanation } from "./ScoreRail";

export function MalLink({ model, onExternal }: { model: RecommendationViewModel; onExternal?: (model: RecommendationViewModel) => void }) {
  const platform = usePlatform();
  if (!model.mal_url) return null;
  return <a className="pill mal-link" href={model.mal_url} target="_blank" rel="noreferrer noopener"
    aria-label={`Open ${model.display_title} on MyAnimeList (external)`}
    onClick={(event) => {
      // Preserve modified clicks and the real href in the browser.
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      void platform.openExternal(model.mal_url!).then(() => onExternal?.(model)).catch(() => {});
    }}>MyAnimeList <span aria-hidden="true">↗</span></a>;
}

/** Native modality supplies focus containment, Escape, and return-to-invoker. */
export function RecommendationDetails({ model, engineId = null, onClose, onExternal }: {
  model: RecommendationViewModel;
  engineId?: string | null;
  onClose: () => void;
  onExternal?: (model: RecommendationViewModel) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const headingId = useId();
  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    return () => node.close();
  }, []);

  return <dialog ref={dialog} className="details-dialog" aria-labelledby={headingId} onClose={() => {
    // StrictMode reopens the same node after effect cleanup. Ignore the
    // queued close event from that rehearsal if it is already open again.
    if (!dialog.current?.open) onClose();
  }}>
    <header className="details-head">
      <span className="lbl">Recommendation inspector</span>
      <button type="button" className="pill" autoFocus onClick={() => dialog.current?.close()}>Close</button>
    </header>
    <h2 id={headingId}>{model.display_title}</h2>
    {model.secondary_title ? <p className="details-secondary">{model.secondary_title}</p> : null}
    <div className="details-fit">
      <span className="lbl">Personal fit</span>
      <strong>{personalFitText(model, engineId)}</strong>
    </div>
    <div className="details-grid">
      <section className="details-explanation" aria-label="Why this pick">
        <h3>Why this pick</h3>
        <WhyExplanation why={model.why} />
      </section>
      <section aria-label="Title information">
        <h3>About this title</h3>
        <dl>
          <dt>Genres</dt><dd>{model.genres.join(" · ") || "Not available"}</dd>
          <dt>Studio</dt><dd>{model.studios.join(" · ") || "Not available"}</dd>
          <dt>Released</dt><dd>{model.year_text || "Not available"}</dd>
          <dt>Episodes</dt><dd>{model.episodes_text || "Not available"}</dd>
          <dt>Status</dt><dd>{model.status || "Not available"}</dd>
          <dt>MAL score</dt><dd>{model.mal_score === null ? "Not rated" : `${model.mal_score.toFixed(2)} / 10`}</dd>
        </dl>
        {model.synopsis ? <p className="details-synopsis">{model.synopsis}</p> : null}
        <MalLink model={model} onExternal={onExternal} />
      </section>
    </div>
  </dialog>;
}
