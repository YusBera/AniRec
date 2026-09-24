/**
 * The Discover instrument header, as `gui/discover_page.py` builds it.
 *
 * One panel, two lines. Line one: the channel, STATE, a sentence beside it,
 * and the one action, RUN ANALYSIS. Line two: the TASTE VECTOR behind the
 * feed, folded to one sentence until EXPAND is chosen.
 *
 * STATE is a fixed vocabulary (READY, BUSY, FAULT) driven only by what the
 * operation is doing; the sentence goes beside it, never inside it (the
 * desktop's comment on `status_label`). The taste sentence is built exactly
 * as `TastePanel._summary_sentence` builds it, from the typed terms the API
 * serves in `feed.taste_vector`: a studio is never worded as a genre.
 */

import { useId, useState } from "react";
import type { TasteVector } from "../api/types";
import { Icon } from "../assets/Icon";

export const DISCOVER_TEXT = {
  channel: "Discover",
  channelMark: "// 推薦",
  stateCaption: "STATE",
  refresh: "RUN ANALYSIS",
  refreshing: "ANALYSING…",
  refreshAccessible: "Update your anime list and pick new recommendations",
  ready: "READY",
  busy: "BUSY",
  fault: "FAULT",
  tasteCaption: "TASTE VECTOR",
  tasteShow: "EXPAND",
  tasteHide: "COLLAPSE",
  tasteEmpty: "Your taste appears here once AniRec has seen your ratings.",
  tasteNoneYet: "nothing yet",
} as const;

/** `TastePanel._summary_sentence`, over the API's typed terms. */
export function tasteSentence(vector: TasteVector | null | undefined): string {
  const liked = vector?.liked ?? [];
  const avoided = vector?.avoided ?? [];
  if (!liked.length && !avoided.length) return DISCOVER_TEXT.tasteEmpty;
  const genres = liked.filter((term) => term.kind === "genre").map((term) => term.term);
  const studios = liked.filter((term) => term.kind === "studio").map((term) => term.term);
  if (genres.length && studios.length) {
    return `You tend to enjoy ${genres.join(", ")}, often from ${studios.slice(0, 2).join(" and ")}.`;
  }
  if (studios.length) return `You tend to reach for work from ${studios.slice(0, 2).join(" and ")}.`;
  return `You tend to enjoy ${genres.join(", ") || DISCOVER_TEXT.tasteNoneYet}.`;
}

/** The expanded lines: `taste_line` for each liked term, `taste_avoid` for each avoided one. */
export function tasteLines(vector: TasteVector | null | undefined): string[] {
  return [
    ...(vector?.liked ?? []).map((term) => `${term.term}: ${term.rated_count} you have finished`),
    ...(vector?.avoided ?? []).map((term) => `${term.term}: usually not for you`),
  ];
}

export type HeaderState = "ready" | "busy" | "fault";

export function DiscoverHeader({ state, message, running, runDisabledReason, onRun, taste }: {
  state: HeaderState;
  message: string;
  running: boolean;
  runDisabledReason: string | null;
  onRun: () => void;
  taste: TasteVector | null | undefined;
}) {
  const [expanded, setExpanded] = useState(false);
  const detailId = useId();
  const messageId = useId();
  const lines = tasteLines(taste);
  const stateText = state === "busy" ? DISCOVER_TEXT.busy : state === "fault" ? DISCOVER_TEXT.fault : DISCOVER_TEXT.ready;

  return <header className="discover-header panel">
    <div className="discover-strip">
      <h1 className="discover-channel">{DISCOVER_TEXT.channel} <span aria-hidden="true">{DISCOVER_TEXT.channelMark}</span></h1>
      <span className="strip-rule" aria-hidden="true" />
      <p className="discover-state" role="status">
        <span className="state-caption">{DISCOVER_TEXT.stateCaption}</span>{" "}
        <span className="state-value" data-tone={state}>{stateText}</span>
        {message ? <span className="state-message" id={messageId}>{message}</span> : null}
      </p>
      <button type="button" className="btn primary run-analysis" disabled={running || runDisabledReason !== null}
        aria-describedby={runDisabledReason && message ? messageId : undefined}
        title={runDisabledReason ?? DISCOVER_TEXT.refreshAccessible} onClick={onRun}>
        <Icon name="refresh" />{running ? DISCOVER_TEXT.refreshing : DISCOVER_TEXT.refresh}
      </button>
    </div>
    <div className="taste-panel">
      <div className="taste-head">
        <h2 className="taste-caption">{DISCOVER_TEXT.tasteCaption}</h2>
        <span className="strip-rule" aria-hidden="true" />
        <p className="taste-summary">{tasteSentence(taste)}</p>
        <button type="button" className="taste-toggle" aria-expanded={expanded} aria-controls={detailId}
          disabled={!lines.length} onClick={() => setExpanded((open) => !open)}>
          <span className="visually-hidden">Taste details: </span>{expanded ? DISCOVER_TEXT.tasteHide : DISCOVER_TEXT.tasteShow}
        </button>
      </div>
      <ul id={detailId} className="taste-lines" hidden={!expanded}>
        {lines.map((line) => <li key={line}>{line}</li>)}
      </ul>
    </div>
  </header>;
}
