/**
 * First run, from the Welcome step of `gui/setup_wizard.py` (`WIZARD_TEXT`).
 *
 * Shown when `/api/system/state` reports `needs_setup`, and remembered for
 * the browser session once dismissed. "Look around with sample data" is the
 * primary action, as it is on the desktop.
 *
 * The desktop's next step asks for a Client ID and opens MyAnimeList's OAuth
 * page. The web client cannot ask a visitor for a Client ID, and the hosted,
 * username-only import waits on D-014, so the connect step says plainly that
 * connecting is not available here yet. It never points anywhere else.
 */

import { useEffect, useId, useRef, useState } from "react";

const SEEN_KEY = "anirec.firstRun.dismissed";

export function firstRunDismissed(): boolean {
  try { return sessionStorage.getItem(SEEN_KEY) === "1"; } catch { return false; }
}

function rememberDismissed() {
  try { sessionStorage.setItem(SEEN_KEY, "1"); } catch { /* private mode: shown again next load */ }
}

export function FirstRun({ step: initialStep = "welcome", onClose }: { step?: "welcome" | "connect"; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [step, setStep] = useState(initialStep);
  const heading = useId();
  const body = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    return () => node.close();
  }, []);
  useEffect(() => { body.current?.querySelector<HTMLElement>("h2")?.focus(); }, [step]);

  const finish = () => { rememberDismissed(); dialog.current?.close(); };

  return <dialog ref={dialog} className="first-run" aria-labelledby={heading}
    onClose={() => { if (!dialog.current?.open) { rememberDismissed(); onClose(); } }}>
    <p className="legend">SET UP ANIREC · STEP {step === "welcome" ? "1" : "2"} OF 2</p>
    <div ref={body}>
      {step === "welcome" ? <>
        <h2 id={heading} tabIndex={-1}>Welcome</h2>
        <p>AniRec uses your MyAnimeList history to build genre-based, explainable anime recommendations. Settings, profile data, and generated results stay in your local AniRec application-data folder. AniRec is an unofficial application and is not affiliated with or endorsed by MyAnimeList.</p>
        <button type="button" className="btn primary first-run-demo" aria-describedby={`${heading}-demo`} onClick={finish}>Look around with sample data</button>
        <p id={`${heading}-demo`}>No account needed. Nothing is saved.</p>
        <p>Or choose Next to read about connecting your MyAnimeList account.</p>
      </> : <>
        <h2 id={heading} tabIndex={-1}>MyAnimeList Setup</h2>
        <p>Connecting a MyAnimeList account is not available in the web client yet.</p>
        <p>Until then, the sample library shows how AniRec picks and explains recommendations. Sample decisions are not saved.</p>
        <button type="button" className="btn primary first-run-demo" onClick={finish}>Look around with sample data</button>
      </>}
    </div>
    <div className="first-run-nav">
      <button type="button" className="btn" disabled={step === "welcome"} onClick={() => setStep("welcome")}>Back</button>
      {step === "welcome" ? <button type="button" className="btn" onClick={() => setStep("connect")}>Next</button> : null}
      <button type="button" className="btn" onClick={finish}>Close</button>
    </div>
  </dialog>;
}
