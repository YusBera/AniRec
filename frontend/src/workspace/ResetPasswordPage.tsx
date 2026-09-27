/**
 * The page an emailed reset link opens (D-021, phase 5): choose a new
 * password. A successful reset signs every device out and does not sign this
 * browser in (the link may be opened anywhere), so the page offers Sign in.
 *
 * The token arrives in the URL fragment, which browsers never send to a
 * server or in a Referer. `takeResetToken` reads it before the first render
 * and removes it from the address bar and the history entry.
 */

import { useEffect, useId, useRef, useState } from "react";
import { AniRecApiError, api } from "../api/client";
import { resetProblem } from "./AccountDialog";
import { PageHeading } from "./common";

export const RESET_ROUTE = "#/reset-password";

// Held in memory only: after the address is cleaned, the token lives nowhere
// else, so a reload asks the reader to open the link again.
let heldToken: string | null = null;

/** The token of an emailed link, taken out of the address. */
export function takeResetToken(): string | null {
  const hash = location.hash;
  if (hash.startsWith(`${RESET_ROUTE}?`)) {
    heldToken = new URLSearchParams(hash.slice(RESET_ROUTE.length + 1)).get("token") || null;
    history.replaceState(history.state, "", `${location.pathname}${location.search}${RESET_ROUTE}`);
    return heldToken;
  }
  return hash === RESET_ROUTE ? heldToken : null;
}

type Outcome = { kind: "form"; problem: string } | { kind: "done" } | { kind: "spent"; message: string };

export function ResetPasswordPage({ token, onSignIn, onAskAgain, onReset }: {
  token: string | null;
  onSignIn: () => void;
  onAskAgain: () => void;
  onReset: () => void;
}) {
  const passwordId = useId();
  const hintId = useId();
  const statusId = useId();
  const [password, setPassword] = useState("");
  const [shown, setShown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>({ kind: "form", problem: "" });
  const signIn = useRef<HTMLButtonElement>(null);
  const askAgain = useRef<HTMLButtonElement>(null);

  // The live region alone is easy to miss: focus goes to the next step.
  useEffect(() => {
    if (outcome.kind === "done") signIn.current?.focus();
    if (outcome.kind === "spent") askAgain.current?.focus();
  }, [outcome.kind]);

  const submit = async () => {
    if (busy || !token) return;
    setBusy(true);
    setOutcome({ kind: "form", problem: "" });
    try {
      const result = await api.confirmPasswordReset(token, password);
      if (!result.reason) {
        heldToken = null;
        setPassword("");
        setOutcome({ kind: "done" });
        onReset();
      } else if (result.reason === "invalid-token") {
        heldToken = null;
        setOutcome({ kind: "spent", message: resetProblem(result.reason) });
      } else {
        // Wrong links count as failed sign-ins for this visitor (limits.py).
        setOutcome({ kind: "form", problem: result.reason === "too-many-attempts"
          ? "Too many attempts. Wait a minute, then try again." : resetProblem(result.reason) });
      }
    } catch (caught) {
      setOutcome({ kind: "form", problem: caught instanceof AniRecApiError && caught.status === 0
        ? "AniRec couldn't reach its local service. Try again in a moment."
        : resetProblem("") });
    } finally {
      setBusy(false);
    }
  };

  const askButton = <button type="button" ref={askAgain} className="btn primary" onClick={onAskAgain}>Email me a new link</button>;

  return <section className="reset-page panel">
    <PageHeading name="Choose a new password" />
    {outcome.kind === "done" ? <>
      <p role="status">Your password was changed, and you're signed out everywhere. Sign in with your new password.</p>
      <button type="button" ref={signIn} className="btn primary" onClick={onSignIn}>Sign in</button>
    </> : outcome.kind === "spent" ? <>
      <p role="status">{outcome.message}</p>
      {askButton}
    </> : !token ? <>
      <p>This link is incomplete. Open the link from your email again, or ask for a new one.</p>
      {askButton}
    </> : <form className="password-form" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <p className="account-lead">Choose a new password for your AniRec account. Every device signed in to it will be signed out.</p>
      <label htmlFor={passwordId}>New password</label>
      <div className="password-field">
        <input id={passwordId} type={shown ? "text" : "password"} autoComplete="new-password" required minLength={8} maxLength={256}
          value={password} disabled={busy} aria-invalid={outcome.problem ? true : undefined}
          aria-describedby={`${hintId} ${statusId}`}
          onChange={(event) => { setPassword(event.target.value); setOutcome({ kind: "form", problem: "" }); }} />
        <button type="button" className="btn show-password" aria-pressed={shown} onClick={() => setShown((value) => !value)}>
          {shown ? "Hide" : "Show"}<span className="visually-hidden"> password</span>
        </button>
      </div>
      <p id={hintId} className="account-hint">At least 8 characters.</p>
      <p id={statusId} className={outcome.problem ? "onboarding-problem" : "onboarding-status"} role="status">
        {busy ? "Saving…" : outcome.problem}
      </p>
      <button type="submit" className="btn primary" disabled={busy}>{busy ? "Saving…" : "Set new password"}</button>
    </form>}
  </section>;
}
