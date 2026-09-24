/**
 * Settings → ACCOUNT (D-021): who you are signed in as, change password,
 * download your data, and delete your account.
 *
 * Deleting names every list it removes before asking, and asks a registered
 * reader for their password. A guest has none; only their own cookie reaches
 * their account.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { AniRecApiError, api } from "../api/client";
import type { AccountSummary } from "../api/types";

const PROBLEMS: Record<string, string> = {
  "wrong-credentials": "That password isn't right.",
  "weak-password": "Use at least 8 characters for the new password.",
  "password-too-long": "That password is too long. Use 256 characters or fewer.",
  "too-many-attempts": "Too many attempts. Wait 15 minutes, then try again.",
  "operation-running": "One of your lists is being updated right now. Try again when it finishes.",
  busy: "AniRec is busy right now. Try again in a minute.",
  "signed-out": "You're signed out. Sign in again first.",
  "session-ended": "You're signed out. Sign in again first.",
};

export const accountManagementProblem = (reason: string) => PROBLEMS[reason] ?? "Something went wrong. Try again.";

function Section({ children }: { children: ReactNode }) {
  const id = useId();
  return <section className="settings-group panel" aria-labelledby={id}><h2 id={id}>ACCOUNT</h2>{children}</section>;
}

function PasswordForm({ onChanged }: { onChanged: () => void }) {
  const currentId = useId();
  const nextId = useId();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  return <form className="password-form" onSubmit={async (event) => {
    event.preventDefault(); setBusy(true); setStatus("");
    try {
      const result = await api.changePassword(current, next);
      if (result.account) { setCurrent(""); setNext(""); setStatus("Password changed. You're still signed in here; everywhere else is signed out."); onChanged(); }
      else setStatus(accountManagementProblem(result.reason ?? ""));
    } catch (caught) { setStatus(caught instanceof AniRecApiError && caught.status === 0 ? "AniRec couldn't reach its local service. Try again in a moment." : accountManagementProblem("")); }
    finally { setBusy(false); }
  }}>
    <h3>Change password</h3>
    <label htmlFor={currentId}>Current password</label>
    <input id={currentId} type="password" autoComplete="current-password" required maxLength={256} value={current} disabled={busy} onChange={(e) => setCurrent(e.target.value)} />
    <label htmlFor={nextId}>New password</label>
    <input id={nextId} type="password" autoComplete="new-password" required minLength={8} maxLength={256} value={next} disabled={busy} onChange={(e) => setNext(e.target.value)} />
    <button className="btn" disabled={busy}>{busy ? "Changing…" : "Change password"}</button>
    <p role="status" className="settings-hint">{status}</p>
  </form>;
}

function DeleteDialog({ registered, onDeleted, onClose }: { registered: boolean; onDeleted: () => void; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useId();
  const passwordId = useId();
  const [lists, setLists] = useState<string[] | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const deleted = useRef(false);
  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    let cancelled = false;
    api.imports().then((read) => { if (!cancelled) setLists(read.imports.map((item) => item.username)); }).catch(() => { if (!cancelled) setLists([]); });
    return () => { cancelled = true; node.close(); };
  }, []);
  const title = registered ? "Delete your account?" : "Delete your data?";
  return <dialog ref={dialog} className="account-dialog" aria-labelledby={heading}
    onClose={() => { if (dialog.current?.open) return; if (deleted.current) onDeleted(); onClose(); }}>
    <h2 id={heading}>{title}</h2>
    <p className="account-lead">This can't be undone. AniRec deletes {registered ? "your account and " : ""}everything saved with it:</p>
    {lists === null ? <p role="status">Loading your lists…</p>
      : lists.length ? <ul className="delete-lists">{lists.map((name) => <li key={name}>{name}'s list, with its Watch Later and Not interested</li>)}</ul>
        : <p>No lists are saved yet.</p>}
    <p className="settings-hint">Your MyAnimeList account and lists are not touched. Download your data first if you want a copy.</p>
    <form onSubmit={async (event) => {
      event.preventDefault(); setBusy(true); setProblem("");
      try {
        const result = await api.deleteAccount(registered ? password : null);
        if (result.reason) setProblem(accountManagementProblem(result.reason));
        else { deleted.current = true; setPassword(""); dialog.current?.close(); }
      } catch { setProblem(accountManagementProblem("")); }
      finally { setBusy(false); }
    }}>
      {registered ? <>
        <label htmlFor={passwordId}>Your password</label>
        <input id={passwordId} type="password" autoComplete="current-password" required maxLength={256} value={password}
          disabled={busy} aria-invalid={problem ? true : undefined} onChange={(e) => { setPassword(e.target.value); setProblem(""); }} />
      </> : null}
      <p role="status" className={problem ? "onboarding-problem" : "onboarding-status"}>{busy ? "Deleting…" : problem}</p>
      <div className="dialog-actions">
        <button type="button" className="btn" onClick={() => dialog.current?.close()}>Keep my {registered ? "account" : "data"}</button>
        <button type="submit" className="btn danger" disabled={busy || lists === null}>{registered ? "Delete my account" : "Delete my data"}</button>
      </div>
    </form>
  </dialog>;
}

export function AccountSection({ account, onAccount }: {
  account: AccountSummary | null;
  onAccount?: (event: "deleted" | "password-changed") => void;
}) {
  const [deleting, setDeleting] = useState(false);
  if (!account) {
    return <Section><p>You're not signed in. Create an account or sign in from the account menu, top right.</p></Section>;
  }
  const registered = account.kind === "registered";
  return <Section>
    <p>{registered ? <>Signed in as <strong>{account.email}</strong>.</> : "You're using AniRec as a guest. Create an account from the account menu to keep your lists."}</p>
    {registered ? <PasswordForm onChanged={() => onAccount?.("password-changed")} /> : null}
    {registered ? <p className="settings-hint">Forgot your password? Resetting it needs email, which this AniRec doesn't send yet.</p> : null}
    <div className="workspace-toolbar">
      {/* A plain download: the browser sends its session cookie with it. */}
      <a className="btn" href={api.exportUrl()} download="anirec-export.json">Download my data</a>
      <button type="button" className="btn danger" onClick={() => setDeleting(true)}>{registered ? "Delete account" : "Delete my data"}</button>
    </div>
    {deleting ? <DeleteDialog registered={registered} onClose={() => setDeleting(false)} onDeleted={() => onAccount?.("deleted")} /> : null}
  </Section>;
}
