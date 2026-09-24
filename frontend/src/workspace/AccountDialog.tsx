/**
 * Create an account, or sign in (D-021): one small dialog with two modes.
 *
 * A guest who creates an account keeps everything: the same account is
 * upgraded, so their list and Watch Later stay where they are. A guest who
 * signs in brings their list along. The session is an HttpOnly cookie the
 * browser keeps; nothing here touches a token.
 */

import { useEffect, useId, useRef, useState } from "react";
import { AniRecApiError, api } from "../api/client";
import type { AccountSummary } from "../api/types";

export type AccountMode = "register" | "sign-in";

/** What a reader reads for each reason the service gives. */
export function accountProblem(reason: string): string {
  switch (reason) {
    case "invalid-email": return "That doesn't look like an email address.";
    case "weak-password": return "Use at least 8 characters for your password.";
    case "password-too-long": return "That password is too long. Use 256 characters or fewer.";
    case "email-taken": return "An account with this email already exists. Sign in instead.";
    case "wrong-credentials": return "That email and password don't match an account.";
    case "too-many-attempts": return "Too many attempts. Wait 15 minutes, then try again.";
    case "already-signed-in": return "You're already signed in. Sign out first to create another account.";
    case "busy": return "AniRec is busy right now. Try again in a minute.";
    default: return "Something went wrong. Try again.";
  }
}

const COPY: Record<AccountMode, { title: string; lead: string; submit: string; busy: string; switchTo: string; switchLabel: string }> = {
  register: {
    title: "Create your account",
    lead: "Keep your list and your Watch Later, every time you come back.",
    submit: "Create account",
    busy: "Creating…",
    switchTo: "Already have an account?",
    switchLabel: "Sign in",
  },
  "sign-in": {
    title: "Welcome back",
    lead: "Sign in to pick up where you left off.",
    submit: "Sign in",
    busy: "Signing in…",
    switchTo: "New to AniRec?",
    switchLabel: "Create an account",
  },
};

export function AccountDialog({ mode: initialMode, onDone, onClose }: {
  mode: AccountMode;
  onDone: (account: AccountSummary, mode: AccountMode, movedImports: number) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const emailField = useRef<HTMLInputElement>(null);
  const heading = useId();
  const emailId = useId();
  const passwordId = useId();
  const hintId = useId();
  const statusId = useId();
  const [mode, setMode] = useState(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [shown, setShown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const done = useRef<{ account: AccountSummary; moved: number } | null>(null);
  const copy = COPY[mode];

  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    return () => node.close();
  }, []);
  useEffect(() => { if (problem) emailField.current?.focus(); }, [problem]);

  const submit = async () => {
    if (busy) return;
    setBusy(true);
    setProblem("");
    try {
      const result = mode === "register" ? await api.register(email.trim(), password) : await api.signIn(email.trim(), password);
      if (result.account) {
        done.current = { account: result.account, moved: result.moved_imports ?? 0 };
        setPassword("");
        dialog.current?.close();
        return;
      }
      setProblem(accountProblem(result.reason ?? ""));
    } catch (caught) {
      setProblem(caught instanceof AniRecApiError && caught.status === 0
        ? "AniRec couldn't reach its local service. Try again in a moment."
        : accountProblem(""));
    } finally {
      setBusy(false);
    }
  };

  return <dialog ref={dialog} className="account-dialog" aria-labelledby={heading}
    onClose={() => {
      if (dialog.current?.open) return;
      if (done.current) onDone(done.current.account, mode, done.current.moved);
      onClose();
    }}>
    <h2 id={heading}>{copy.title}</h2>
    <p className="account-lead">{copy.lead}</p>
    <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <label htmlFor={emailId}>Email</label>
      <input id={emailId} ref={emailField} type="email" autoComplete="email" required maxLength={254}
        value={email} disabled={busy} aria-describedby={statusId} aria-invalid={problem ? true : undefined}
        onChange={(event) => { setEmail(event.target.value); setProblem(""); }} />
      <label htmlFor={passwordId}>Password</label>
      <div className="password-field">
        <input id={passwordId} type={shown ? "text" : "password"} required maxLength={256}
          autoComplete={mode === "register" ? "new-password" : "current-password"}
          value={password} disabled={busy} aria-invalid={problem ? true : undefined}
          aria-describedby={mode === "register" ? `${hintId} ${statusId}` : statusId}
          onChange={(event) => { setPassword(event.target.value); setProblem(""); }} />
        <button type="button" className="btn show-password" aria-pressed={shown} onClick={() => setShown((value) => !value)}>
          {shown ? "Hide" : "Show"}<span className="visually-hidden"> password</span>
        </button>
      </div>
      {mode === "register" ? <p id={hintId} className="account-hint">At least 8 characters.</p> : null}
      {/* One live region for progress and problems (as in FirstRun). */}
      <p id={statusId} className={problem ? "onboarding-problem" : "onboarding-status"} role="status">
        {busy ? copy.busy : problem}
      </p>
      <button type="submit" className="btn primary account-submit" disabled={busy}>{busy ? copy.busy : copy.submit}</button>
    </form>
    <p className="account-switch">{copy.switchTo}{" "}
      <button type="button" className="link-button" onClick={() => { setMode(mode === "register" ? "sign-in" : "register"); setProblem(""); }}>
        {copy.switchLabel}
      </button>
    </p>
    <button type="button" className="onboarding-close" aria-label="Close" onClick={() => dialog.current?.close()}>×</button>
  </dialog>;
}
