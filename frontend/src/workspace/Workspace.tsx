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
import type { Feed } from "../api/types";
import { DiscoverPage } from "../discover/DiscoverPage";
import { ProfilePage } from "./ProfilePage";
import { ComparePage } from "./ComparePage";
import { SettingsPage } from "./SettingsPage";
import { FirstRun, firstRunDismissed } from "./FirstRun";
import { useShellState } from "./Shell";
import { TopBar, useAvatar } from "./TopBar";
import "./workspace.css";

const titles: Record<string, string> = {
  discover: "Discover", library: "My Library", profile: "Profile", compare: "Compare", settings: "Settings",
};
type Page = "discover" | "library" | "profile" | "compare" | "settings";
const route = (): Page => (Object.keys(titles).find((id) => location.hash === `#/${id}`) ?? "discover") as Page;

export function Workspace() {
  const [page, setPage] = useState<Page>(route);
  const [visited, setVisited] = useState<Set<Page>>(() => new Set([route()]));
  const [feed, setFeed] = useState<Feed | null>(null);
  const [firstRun, setFirstRun] = useState<null | "welcome">(null);
  const shell = useShellState();
  const content = useRef<HTMLDivElement>(null);
  const positions = useRef<Partial<Record<Page, number>>>({});
  const active = useRef(page);

  useEffect(() => {
    const change = () => {
      if (!location.hash.startsWith("#/")) return;
      const next = route();
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
    if (shell.system?.needs_setup && !firstRunDismissed()) setFirstRun((current) => current ?? "welcome");
  }, [shell.system?.needs_setup]);

  const onFeedChange = useCallback((next: Feed | null) => setFeed(next), []);
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
    <TopBar page={page} system={shell.system} feed={feed} notices={shell.notices} avatarUrl={avatarUrl} />
    <div className="workspace-content" ref={content} id="workspace-content" tabIndex={-1}>
      {/* No "Connect my account" here: connecting an account from the web
          client is not possible (user decision, 2026-09-24). */}
      {sample ? <div className="sample-banner" role="note">
        <p>You're exploring a sample library. Try anything; nothing here is saved.</p>
      </div> : null}
      <DiscoverPage surface={page === "discover" || page === "library" ? page : "inactive"}
        onFeedChange={onFeedChange} onOperationStarted={shell.nudge} autoRefresh
        activeProfileId={shell.system?.profile?.profile_id ?? null} />
      <div hidden={page !== "profile"}>{visited.has("profile") ? <ProfilePage /> : null}</div>
      <div hidden={page !== "compare"}>{visited.has("compare") ? <ComparePage /> : null}</div>
      <div hidden={page !== "settings"}>{visited.has("settings") ? <SettingsPage version={shell.version} /> : null}</div>
    </div>
    {firstRun ? <FirstRun onClose={() => setFirstRun(null)} /> : null}
  </div>;
}
