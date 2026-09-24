/**
 * The workspace shell (D-019): a top bar with the pages as tabs and, top
 * right, notifications and the account picture, as on the sites a newcomer
 * already uses. Profile and Settings are reached from the picture. Sample
 * data stays visibly labelled for as long as it is on screen.
 *
 * Hash routes keep each visited page mounted, so its state survives
 * navigation, and focus moves to the page heading on every route change.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Feed } from "../api/types";
import { AccountDialog, type AccountMode } from "./AccountDialog";
import { DiscoverPage } from "../discover/DiscoverPage";
import { ProfilePage } from "./ProfilePage";
import { ComparePage } from "./ComparePage";
import { SettingsPage } from "./SettingsPage";
import { ResetPasswordPage, takeResetToken } from "./ResetPasswordPage";
import { FirstRun, firstRunDismissed } from "./FirstRun";
import { useShellState } from "./Shell";
import { TopBar, useAvatar, type AccountAction } from "./TopBar";
import "./workspace.css";

const titles: Record<string, string> = {
  discover: "Discover", library: "My Library", profile: "Profile", compare: "Compare", settings: "Settings",
  "reset-password": "Reset password",
};
type Page = "discover" | "library" | "profile" | "compare" | "settings" | "reset-password";
const SAVE_PROMPT_KEY = "anirec.savePrompt.dismissed";
const savePromptDismissed = () => { try { return sessionStorage.getItem(SAVE_PROMPT_KEY) === "1"; } catch { return false; } };

// The query after a route (only the reset link carries one) is not the route.
const route = (): Page => (Object.keys(titles).find((id) => location.hash.split("?")[0] === `#/${id}`) ?? "discover") as Page;

export function Workspace() {
  // Before the first render: the emailed token leaves the address at once.
  const [resetToken, setResetToken] = useState(takeResetToken);
  const [page, setPage] = useState<Page>(route);
  const [visited, setVisited] = useState<Set<Page>>(() => new Set([route()]));
  const [feed, setFeed] = useState<Feed | null>(null);
  const [firstRun, setFirstRun] = useState<null | "welcome">(null);
  const [accountDialog, setAccountDialog] = useState<AccountMode | null>(null);
  // Bumped when the signed-in account changes: every page remounts and reads
  // the new account's data, so nothing from the previous one stays on screen.
  const [generation, setGeneration] = useState(0);
  const [promptHidden, setPromptHidden] = useState(savePromptDismissed);
  const shell = useShellState();
  const content = useRef<HTMLDivElement>(null);
  const positions = useRef<Partial<Record<Page, number>>>({});
  const active = useRef(page);

  useEffect(() => {
    const change = () => {
      if (!location.hash.startsWith("#/")) return;
      const next = route();
      // A reset link opened in a tab that already shows AniRec.
      if (next === "reset-password") setResetToken(takeResetToken());
      positions.current[active.current] = window.scrollY;
      active.current = next;
      setPage(next);
      setVisited(previous => new Set([...previous, next]));
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    document.title = `${titles[page]} · AniRec`;
    const heading = [...(content.current?.querySelectorAll<HTMLElement>("h1") ?? [])].find(node => !node.closest("[hidden]"));
    heading?.setAttribute("tabindex", "-1");
    heading?.focus({ preventScroll: true });
    window.scrollTo(0, positions.current[page] ?? 0);
  }, [page]);
  // First run: when the service says setup is needed, once per session.
  useEffect(() => {
    // A reader who already has a profile is never interrupted by it, nor is
    // one choosing a new password from an emailed link.
    if (page === "reset-password") { setFirstRun(null); return; }
    if (shell.system?.needs_setup && !shell.system.profile && !firstRunDismissed()) setFirstRun((current) => current ?? "welcome");
  }, [shell.system?.needs_setup, shell.system?.profile, page]);

  const onFeedChange = useCallback((next: Feed | null) => setFeed(next), []);
  const accountChanged = useCallback(() => {
    setFeed(null);
    setVisited(new Set([active.current]));
    setGeneration((value) => value + 1);
    shell.reset();
  }, [shell.reset]);
  const onAccount = useCallback((action: AccountAction, username?: string) => {
    if (action === "list-changed") {
      // Same reader, another of their lists: reload the pages, keep the bell,
      // say so, and start again from the page (the menu that had focus is gone).
      setFeed(null);
      setGeneration((value) => value + 1);
      shell.nudge();
      if (username) shell.notify({ tone: "done", title: `Showing ${username}'s list` });
      content.current?.focus();
      return;
    }
    if (action !== "sign-out") { setAccountDialog(action); return; }
    api.signOut().then(() => {
      accountChanged();
      shell.notify({ tone: "info", title: "Signed out", detail: "Sign in again to see your list." });
    }).catch(() => shell.notify({ tone: "problem", title: "Signing out didn't finish", detail: "Try again in a moment." }));
  }, [accountChanged, shell.notify, shell.nudge]);
  const account = shell.system?.account ?? null;
  // A rebuild started by saving preferences: follow it by its own id until it
  // ends, then reload the pages (Discover follows only the runs it started).
  const [rebuild, setRebuild] = useState<string | null>(null);
  const onPreferencesChanged = useCallback(() => {
    api.startOperation("recommendation").then((operation) => {
      setRebuild(operation.id);
      shell.nudge();
    }).catch(() => shell.notify({ tone: "problem", title: "Your recommendations weren't updated", detail: "Your preferences are saved; they apply the next time your recommendations are rebuilt." }));
  }, [shell.nudge, shell.notify]);
  useEffect(() => {
    if (!rebuild) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const check = () => {
      api.operation(rebuild).then((operation) => {
        if (cancelled) return;
        if (operation.state === "running") { timer = setTimeout(check, 2000); return; }
        setRebuild(null); setFeed(null); setGeneration((value) => value + 1);
      }).catch(() => { if (!cancelled) timer = setTimeout(check, 5000); });
    };
    check();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [rebuild]);
  const onSettingsAccount = useCallback((event: "deleted" | "password-changed") => {
    if (event === "deleted") {
      accountChanged();
      shell.notify({ tone: "info", title: "Your account was deleted", detail: "You can keep looking around." });
    } else {
      shell.notify({ tone: "done", title: "Password changed", detail: "You're still signed in here; everywhere else is signed out." });
    }
  }, [accountChanged, shell.notify]);
  // "Try first, then register": a guest with something saved is reminded,
  // gently and dismissibly, that it lives only in this browser (D-021).
  const showSavePrompt = account?.kind === "guest" && account.has_import && !promptHidden
    && (page === "discover" || page === "library");
  const sample = feed?.source === "sample";
  const avatarUrl = useAvatar(shell.system);
  // Said once in the bell as well as on the page, where it stays.
  const sampleNoted = useRef(false);
  useEffect(() => {
    if (!sample || sampleNoted.current) return;
    sampleNoted.current = true;
    shell.notify({ tone: "info", title: "You're exploring the sample library", detail: "Try anything. Nothing you do here is saved." });
  }, [sample, shell.notify]);

  return <div className="workspace">
    <a className="skip-link" href="#workspace-content">Skip to content</a>
    <TopBar page={page} system={shell.system} feed={feed} notices={shell.notices} avatarUrl={avatarUrl}
      onSetUp={() => setFirstRun("welcome")} onAccount={onAccount} />
    <div className="workspace-content" ref={content} id="workspace-content" tabIndex={-1}>
      {/* No "Connect my account" here: connecting an account from the web
          client is not possible (user decision, 2026-09-24). */}
      {sample && page !== "reset-password" ? <div className="sample-banner" role="note">
        <p>You're exploring a sample library. Try anything; nothing here is saved.</p>
      </div> : null}
      {showSavePrompt ? <section className="save-prompt" aria-label="Keep your list">
        <p>Create an account so you don't lose your Watch Later.</p>
        <button type="button" className="btn primary" onClick={() => setAccountDialog("register")}>Create account</button>
        <button type="button" className="btn" onClick={() => {
          setPromptHidden(true);
          try { sessionStorage.setItem(SAVE_PROMPT_KEY, "1"); } catch { /* shown again next load */ }
        }}>Not now</button>
      </section> : null}
      <DiscoverPage key={generation} surface={page === "discover" || page === "library" ? page : "inactive"}
        onFeedChange={onFeedChange} onOperationStarted={shell.nudge} autoRefresh
        activeProfileId={shell.system?.profile?.profile_id ?? null} />
      <div hidden={page !== "profile"}>{visited.has("profile") ? <ProfilePage key={generation} /> : null}</div>
      <div hidden={page !== "compare"}>{visited.has("compare") ? <ComparePage key={generation} /> : null}</div>
      <div hidden={page !== "settings"}>{visited.has("settings") ? <SettingsPage key={generation} version={shell.version}
        account={account} resetAvailable={!!shell.system?.password_reset_available}
        onAccount={onSettingsAccount} onPreferencesChanged={onPreferencesChanged} /> : null}</div>
      <div hidden={page !== "reset-password"}>{page === "reset-password" ? <ResetPasswordPage token={resetToken}
        onSignIn={() => setAccountDialog("sign-in")} onAskAgain={() => setAccountDialog("reset")}
        onReset={() => {
          // Every session of that account ended, perhaps this browser's too.
          accountChanged();
          shell.notify({ tone: "done", title: "Password changed", detail: "Sign in with your new password." });
        }} /> : null}</div>
    </div>
    {firstRun ? <FirstRun clientIdPresent={!!shell.system?.mal_client_id_present}
      onImported={(profile) => {
        shell.notify({ tone: "done", title: `Added ${profile.username}'s MyAnimeList list`, detail: "AniRec is reading it now." });
        // The new list is now the one shown: reload the pages for it; its
        // automatic refresh (D-018) builds the first feed.
        onAccount("list-changed");
      }}
      onClose={() => setFirstRun(null)}
      // Only someone not signed in to an account can have one to sign in to.
      onSignIn={account?.kind === "registered" ? undefined : () => setAccountDialog("sign-in")} /> : null}
    {accountDialog ? <AccountDialog mode={accountDialog} resetAvailable={!!shell.system?.password_reset_available}
      onDone={(signed, mode, moved) => {
        // Signed in after a reset: on to the reader's picks.
        if (active.current === "reset-password") location.hash = "#/discover";
        accountChanged();
        shell.notify(mode === "register"
          ? { tone: "done", title: "Account created", detail: signed.has_import ? "Your list and Watch Later are saved to it." : "Add your MyAnimeList list from the account menu." }
          : { tone: "done", title: "Signed in", detail: moved
            ? "The list you added before signing in is saved to your account. Switch to it from the account menu, under Your lists."
            : signed.email ?? "" });
        // The menu item that opened the dialog is gone; start from the page.
        content.current?.focus();
      }}
      onClose={() => setAccountDialog(null)} /> : null}
  </div>;
}
