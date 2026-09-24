/**
 * First run, from the Welcome step of `gui/setup_wizard.py` (`WIZARD_TEXT`).
 *
 * Shown when `/api/system/state` reports `needs_setup`, and remembered for
 * the browser session once dismissed. "Look around with sample data" is the
 * primary action, as it is on the desktop.
 *
 * The desktop's later steps ask for a Client ID and open MyAnimeList's OAuth
 * page. Connecting an account from the web client is not possible (user
 * decision, 2026-09-24), so only the Welcome step is ported and nothing here
 * offers or promises a connection.
 */

import { useEffect, useId, useRef } from "react";

const SEEN_KEY = "anirec.firstRun.dismissed";

export function firstRunDismissed(): boolean {
  try { return sessionStorage.getItem(SEEN_KEY) === "1"; } catch { return false; }
}

function rememberDismissed() {
  try { sessionStorage.setItem(SEEN_KEY, "1"); } catch { /* private mode: shown again next load */ }
}

export function FirstRun({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useId();
  const body = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    return () => node.close();
  }, []);
  useEffect(() => { body.current?.querySelector<HTMLElement>("h2")?.focus(); }, []);

  const finish = () => { rememberDismissed(); dialog.current?.close(); };

  return <dialog ref={dialog} className="first-run" aria-labelledby={heading}
    onClose={() => { if (!dialog.current?.open) { rememberDismissed(); onClose(); } }}>
    <p className="legend">WELCOME TO ANIREC</p>
    <div ref={body}>
        <h2 id={heading} tabIndex={-1}>Welcome</h2>
        <p>AniRec uses your MyAnimeList history to build genre-based, explainable anime recommendations. Settings, profile data, and generated results stay in your local AniRec application-data folder. AniRec is an unofficial application and is not affiliated with or endorsed by MyAnimeList.</p>
        <button type="button" className="btn primary first-run-demo" aria-describedby={`${heading}-demo`} onClick={finish}>Look around with sample data</button>
        <p id={`${heading}-demo`}>No account needed. Nothing is saved.</p>
    </div>
    <div className="first-run-nav">
      <button type="button" className="btn" onClick={finish}>Close</button>
    </div>
  </dialog>;
}
