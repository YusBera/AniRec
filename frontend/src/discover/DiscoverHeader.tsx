/**
 * The Discover heading (D-019): the page's name and one line saying what it
 * is, as any site introduces a page. While the feed is being updated, a
 * plain sentence says so; nothing is shown when there is nothing to report.
 *
 * The desktop's instrument strip (STATE: READY / BUSY / FAULT) is not
 * ported: a newcomer should not have to read machine state. A failure is
 * reported where it happened, in the control bar's alert.
 *
 * Also not ported, by the user's decision (2026-09-24):
 * - RUN ANALYSIS: feeds refresh by themselves (D-018).
 * - The TASTE VECTOR line: the feed is ranked by a sequence model that never
 *   sees genres, so "You tend to enjoy ..." above it would read as the feed's
 *   reason when it is not (D-012). The reader's taste is described on Profile.
 */

export const DISCOVER_TEXT = {
  title: "Discover",
  intro: "Anime picked for you.",
  updating: "Updating your recommendations…",
} as const;

export function DiscoverHeader({ busy, detail }: { busy: boolean; detail?: string | null }) {
  return <header className="page-header">
    <h1>{DISCOVER_TEXT.title}</h1>
    <p className="workspace-intro">{DISCOVER_TEXT.intro}</p>
    {/* Announced once when an update starts; the progress bar carries each
        stage, so the stage text is not live here. */}
    <p className="page-status" role="status">{busy ? DISCOVER_TEXT.updating : ""}
      {busy && detail ? <span className="page-status-detail" aria-live="off"> {detail}</span> : null}</p>
  </header>;
}
