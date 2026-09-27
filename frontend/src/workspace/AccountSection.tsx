/**
 * Settings → ACCOUNT (D-021): who you are signed in as, change password,
 * a reset link by email for a forgotten one, download your data, and delete
 * your account.
 *
 * Deleting names every list it removes before asking, and asks a registered
 * reader for their password. A guest has none; only their own cookie reaches
 * their account.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { AniRecApiError, api } from "../api/client";
import type { AccountSummary } from "../api/types";
import { resetProblem } from "./AccountDialog";

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

/** A reset link to the account's own email, for a forgotten password. */
function ResetLink({ email, available }: { email: string; available: boolean }) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  if (!available) {
    return <p className="settings-hint">Forgot your password? This AniRec isn't set up to send email, so it can't send you a reset link.</p>;
  }
  return <div className="reset-link">
    <p className="settings-hint">Forgot your password? AniRec can email you a link to choose a new one.</p>
    <button type="button" className="btn" disabled={busy} onClick={async () => {
      setBusy(true); setStatus("");
      try {
        const result = await api.requestPasswordReset(email);
        setStatus(result.reason ? resetProblem(result.reason)
          : `A reset link is on its way to ${email}, unless several were sent this hour. It works for 30 minutes.`);
      } catch (caught) {
        setStatus(caught instanceof AniRecApiError && caught.status === 0 ? "AniRec couldn't reach its local service. Try again in a moment." : resetProblem(""));
      } finally { setBusy(false); }
    }}>{busy ? "Sending…" : "Email me a reset link"}</button>
    <p role="status" className="settings-hint">{status}</p>
  </div>;
}

/** Saves the export through a temporary link, and says so when it can't. */
function DownloadButton() {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  return <>
    <button type="button" className="btn" disabled={busy} onClick={async () => {
      setBusy(true); setStatus("");
      try {
        const blob = await api.exportAccount();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url; link.download = "anirec-export.json";
        document.body.append(link); link.click(); link.remove();
        URL.revokeObjectURL(url);
        setStatus("Your data was downloaded as anirec-export.json.");
      } catch (caught) {
        const status = caught instanceof AniRecApiError ? caught.status : -1;
        setStatus(status === 429 ? "You've downloaded your data several times this hour. Try again later."
          : status === 0 ? "AniRec couldn't reach its local service. Try again in a moment."
            : status === 401 ? "You're signed out. Sign in again first."
              : "Your data couldn't be downloaded. Try again.");
      } finally { setBusy(false); }
    }}>{busy ? "Preparing…" : "Download my data"}</button>
    <p role="status" className="settings-hint download-status">{status}</p>
  </>;
}

function DeleteDialog({ registered, onDeleted, onClose }: { registered: boolean; onDeleted: () => void; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useId();
  const passwordId = useId();
  const [lists, setLists] = useState<{ deleted: string[]; kept: string[] } | null | "failed">(null);
  const [attempt, setAttempt] = useState(0);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const deleted = useRef(false);
  useEffect(() => {
    const node = dialog.current!;
    if (!node.open) node.showModal();
    return () => node.close();
  }, []);
  useEffect(() => {
    let cancelled = false;
    setLists(null);
    api.imports().then((read) => {
      if (cancelled) return;
      if (read.reason) { setLists("failed"); return; }
      setLists({
        deleted: read.imports.filter((item) => !item.kept_on_delete).map((item) => item.username),
        kept: read.imports.filter((item) => item.kept_on_delete).map((item) => item.username),
      });
    }).catch(() => { if (!cancelled) setLists("failed"); });
    return () => { cancelled = true; };
  }, [attempt]);
  const known = lists !== null && lists !== "failed";
  const title = registered ? "Delete your account?" : "Delete your data?";
  return <dialog ref={dialog} className="account-dialog" aria-labelledby={heading}
    onClose={() => { if (dialog.current?.open) return; if (deleted.current) onDeleted(); onClose(); }}>
    <h2 id={heading}>{title}</h2>
    <p className="account-lead">This can't be undone.</p>
    {lists === null ? <p role="status">Loading your lists…</p>
      : lists === "failed" ? <div role="alert"><p>Your lists couldn't be read, so AniRec can't show what would be deleted.</p>
          <button type="button" className="btn" onClick={() => setAttempt((value) => value + 1)}>Try again</button></div>
        : <>
          <p>AniRec deletes {registered ? "your account" : "your guest data"}{lists.deleted.length ? " and these lists, with their Watch Later and Not interested:" : ". No lists would be deleted."}</p>
          {lists.deleted.length ? <ul className="delete-lists">{lists.deleted.map((name) => <li key={name}>{name}'s list</li>)}</ul> : null}
          {lists.kept.length ? <>
            <p>Kept, because the desktop app uses {lists.kept.length === 1 ? "it" : "them"}:</p>
            <ul className="delete-lists">{lists.kept.map((name) => <li key={name}>{name}'s list</li>)}</ul>
          </> : null}
        </>}
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
        <button type="submit" className="btn danger" disabled={busy || !known}>{registered ? "Delete my account" : "Delete my data"}</button>
      </div>
    </form>
  </dialog>;
}

export function AccountSection({ account, resetAvailable = false, onAccount }: {
  account: AccountSummary | null;
  /** Whether this installation can email a reset link (from the system state). */
  resetAvailable?: boolean;
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
    {registered && account.email ? <ResetLink email={account.email} available={resetAvailable} /> : null}
    <div className="workspace-toolbar">
      <DownloadButton />
      <button type="button" className="btn danger" onClick={() => setDeleting(true)}>{registered ? "Delete account" : "Delete my data"}</button>
    </div>
    {deleting ? <DeleteDialog registered={registered} onClose={() => setDeleting(false)} onDeleted={() => onAccount?.("deleted")} /> : null}
  </Section>;
}
