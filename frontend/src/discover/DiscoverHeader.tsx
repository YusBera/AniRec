/**
 * The Discover instrument header, after `gui/discover_page.py`.
 *
 * One line: the channel and STATE, with a sentence beside it. STATE is a
 * fixed vocabulary (READY, BUSY, FAULT) driven only by what the operation is
 * doing; the sentence goes beside it, never inside it (the desktop's comment
 * on `status_label`).
 *
 * Deliberately not ported, by the user's decision (2026-09-24):
 * - RUN ANALYSIS: feeds are not generated from this button.
 * - The TASTE VECTOR line: the feed is ranked by a sequence model that never
 *   sees genres, so "You tend to enjoy ..." above it would read as the feed's
 *   reason when it is not (D-012). The reader's taste is described on Profile.
 */

export const DISCOVER_TEXT = {
  channel: "Discover",
  stateCaption: "STATE",
  ready: "READY",
  busy: "BUSY",
  fault: "FAULT",
} as const;

export type HeaderState = "ready" | "busy" | "fault";

export function DiscoverHeader({ state, message }: { state: HeaderState; message: string }) {
  const stateText = state === "busy" ? DISCOVER_TEXT.busy : state === "fault" ? DISCOVER_TEXT.fault : DISCOVER_TEXT.ready;

  return <header className="discover-header panel">
    <div className="discover-strip">
      <h1 className="discover-channel">{DISCOVER_TEXT.channel}</h1>
      <span className="strip-rule" aria-hidden="true" />
      <p className="discover-state">
        <span role="status">
          <span className="state-caption">{DISCOVER_TEXT.stateCaption}</span>{" "}
          <span className="state-value" data-tone={state}>{stateText}</span>
        </span>
        {/* The stage sentence is not live while BUSY: the progress bar
            already reports it, and announcing both repeats every stage. */}
        {message ? <span className="state-message" aria-live={state === "busy" ? "off" : "polite"}>{message}</span> : null}
      </p>
    </div>
  </header>;
}
