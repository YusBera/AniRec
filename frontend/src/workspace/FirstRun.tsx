/**
 * First-time setup (D-020): one pop-up, welcome on the left, the ways to
 * start on the right.
 *
 * - **MyAnimeList:** type a username; AniRec reads the public list with this
 *   installation's own Client ID. The visitor never enters a Client ID and is
 *   never sent to a MyAnimeList login (D-017 still holds for those).
 * - **AniList, AniDB:** named, marked "Coming soon", and not interactive, so
 *   nothing invites a click that does nothing.
 * - **I'm new to anime:** shown, not active yet. It will be a short poster
 *   picker; it needs a profile that is not a MyAnimeList list first.
 * - **Just look around:** the labelled sample library; nothing is saved.
 *
 * Shown when `/api/system/state` reports `needs_setup`, remembered for the
 * session once closed, and reachable again from the account menu.
 */

import { useEffect, useId, useRef, useState } from "react";
import { AniRecApiError, api } from "../api/client";
import type { ProfileSummary } from "../api/types";

const SEEN_KEY = "anirec.firstRun.dismissed";

export function firstRunDismissed(): boolean {
  try { return sessionStorage.getItem(SEEN_KEY) === "1"; } catch { return false; }
}

function rememberDismissed() {
  try { sessionStorage.setItem(SEEN_KEY, "1"); } catch { /* private mode: shown again next load */ }
}

/** What a newcomer reads for each reason the service gives. */
export function importProblem(reason: string, username: string): string {
  switch (reason) {
    case "invalid-username": return "That doesn't look like a MyAnimeList username. Usernames use letters, numbers and underscores.";
    case "client-id-required": return "MyAnimeList import isn't set up for this AniRec installation yet.";
    case "user-not-found": return `MyAnimeList has no user called ${username}. Check the spelling and try again.`;
    case "private-list": return `${username}'s anime list isn't public, so AniRec can't read it. Make it public on MyAnimeList, then try again.`;
    case "rate-limited": return "MyAnimeList is busy right now. Try again in a minute.";
    case "network": return "AniRec couldn't reach MyAnimeList. Check your connection and try again.";
    default: return "Something went wrong while reading that list. Try again.";
  }
}

const SOON = [["AniList", "anilist"], ["AniDB", "anidb"]] as const;

export function FirstRun({ clientIdPresent, onImported, onClose }: {
  /** From `/api/system/state`: whether this installation can read MyAnimeList lists. */
  clientIdPresent: boolean;
  onImported: (profile: ProfileSummary) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const heading = useId();
  const fieldId = useId();
  const statusId = useId();
  const newcomerId = useId();
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const imported = useRef<ProfileSummary | null>(null);

  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    return () => node.close();
  }, []);

  const close = () => { rememberDismissed(); dialog.current?.close(); };

  const submit = async () => {
    const name = username.trim();
    if (!name || busy) return;
    setBusy(true);
    setProblem("");
    try {
      const result = await api.importMalProfile(name);
      if (result.profile) {
        imported.current = result.profile;
        close();
        return;
      }
      setProblem(importProblem(result.reason ?? "", name));
    } catch (caught) {
      setProblem(caught instanceof AniRecApiError && caught.status === 0
        ? "AniRec couldn't reach its local service. Try again in a moment."
        : importProblem("", name));
    } finally {
      setBusy(false);
    }
  };
  // Put the reader back in the field to fix what the message describes.
  useEffect(() => { if (problem) input.current?.focus(); }, [problem]);

  return <dialog ref={dialog} className="onboarding" aria-labelledby={heading}
    onClose={() => {
      if (dialog.current?.open) return;
      rememberDismissed();
      if (imported.current) onImported(imported.current);
      onClose();
    }}>
    <section className="onboarding-welcome">
      <h2 id={heading}>Welcome to AniRec</h2>
      <p>your personal anime recommender</p>
    </section>

    <section className="onboarding-start" aria-label="Ways to start">
      <form className="source-row" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
        <label className="source-name" htmlFor={fieldId}>MyAnimeList</label>
        <div className="source-field">
          <input id={fieldId} ref={input} type="text" placeholder="Your username" autoComplete="off" spellCheck={false}
            maxLength={100} value={username} disabled={!clientIdPresent || busy}
            aria-describedby={statusId} aria-invalid={problem ? true : undefined}
            onChange={(event) => { setUsername(event.target.value); setProblem(""); }} />
          <button type="submit" className="btn primary source-go" disabled={!clientIdPresent || busy || !username.trim()}
            aria-label="Continue with MyAnimeList">{busy ? "Reading…" : "Continue"}</button>
        </div>
      </form>
      <p id={statusId} className={problem ? "onboarding-problem" : "onboarding-status"} role={problem ? "alert" : "status"}>
        {!clientIdPresent ? importProblem("client-id-required", "")
          : busy ? "Reading your MyAnimeList list…"
            : problem}
      </p>

      {SOON.map(([name, key]) => <div className="source-row" data-soon key={key}>
        <span className="source-name">{name}</span>
        <span className="soon-label">Coming soon</span>
      </div>)}

      <div className="onboarding-or" aria-hidden="true"><span>or</span></div>
      {/* Not active yet: it becomes the poster picker. aria-disabled keeps it
          focusable, so a screen reader hears why rather than skipping it. */}
      <button type="button" className="btn newcomer" aria-disabled="true" aria-describedby={newcomerId}
        onClick={(event) => event.preventDefault()}>I'm new to anime</button>
      <p id={newcomerId} className="soon-label">Coming soon: pick a few that look good, and start from there.</p>

      <button type="button" className="look-around" onClick={close}>Just look around</button>
      <p className="onboarding-status">The sample library. Nothing is saved.</p>
    </section>
    <button type="button" className="onboarding-close" aria-label="Close" onClick={close}>×</button>
  </dialog>;
}
