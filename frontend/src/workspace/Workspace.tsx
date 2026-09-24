/**
 * The workspace shell, as `gui/main_window.py` builds it: the brand plate,
 * the numbered navigation rail, the SYSTEM readout, the ACTIVITY console at
 * the foot of the rail and the BUILD line; and, over the content, the sample
 * banner for as long as sample data is on screen.
 *
 * Hash routes keep each visited page mounted, so its state survives
 * navigation, and focus moves to the page heading on every route change.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Feed } from "../api/types";
import { Icon, type IconName } from "../assets/Icon";
import { DiscoverPage } from "../discover/DiscoverPage";
import { ProfilePage } from "./ProfilePage";
import { ComparePage } from "./ComparePage";
import { SettingsPage } from "./SettingsPage";
import { FirstRun, firstRunDismissed } from "./FirstRun";
import { ActivityConsole, readoutRows, SystemReadout, useShellState } from "./Shell";
import "./workspace.css";

const pages: readonly [string, string, IconName, string][] = [
  ["discover", "Discover", "nav-discover", "Anime picked for you, and the taste behind them."],
  ["library", "My Library", "nav-library", "Everything you have saved, or passed on."],
  ["profile", "Profile", "profile", "The shape of your taste, read off your own ratings."],
  ["compare", "Compare", "nav-compare", "How your taste lines up with someone else's."],
  ["settings", "Settings", "nav-settings", "Your account, how AniRec picks, and your data."],
];
type Page = "discover" | "library" | "profile" | "compare" | "settings";
const route = (): Page => (pages.find(([id]) => location.hash === `#/${id}`)?.[0] ?? "discover") as Page;

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
    document.title = `${pages.find(([id]) => id === page)?.[1]} · AniRec`;
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

  return <div className="workspace">
    <a className="skip-link" href="#workspace-content">Skip to content</a>
    <aside className="workspace-nav">
      <div className="workspace-brand"><span>ANIREC</span></div>
      <nav aria-label="Main navigation">{pages.map(([id, label, icon, description], i) => <a href={`#/${id}`} key={id}
        aria-current={page === id ? "page" : undefined} title={description}>
        <Icon name={icon} className="nav-icon" /><span className="nav-index" aria-hidden="true">0{i + 1}</span><span className="nav-label">{label}</span>
      </a>)}</nav>
      <div className="rail-panels">
        <SystemReadout rows={readoutRows(shell.system, shell.systemFailed, feed)} />
        <ActivityConsole lines={shell.lines} />
        <p className="rail-footer">BUILD {shell.version ?? "unavailable"}</p>
      </div>
    </aside>
    <div className="workspace-content" ref={content} id="workspace-content" tabIndex={-1}>
      {/* No "Connect my account" here: connecting an account from the web
          client is not possible (user decision, 2026-09-24). */}
      {sample ? <div className="sample-banner" role="note">
        <p>Sample data. These are bundled demonstration picks, not your own.</p>
      </div> : null}
      <DiscoverPage surface={page === "discover" || page === "library" ? page : "inactive"}
        onFeedChange={onFeedChange} onOperationStarted={shell.nudge} />
      <div hidden={page !== "profile"}>{visited.has("profile") ? <ProfilePage /> : null}</div>
      <div hidden={page !== "compare"}>{visited.has("compare") ? <ComparePage /> : null}</div>
      <div hidden={page !== "settings"}>{visited.has("settings") ? <SettingsPage /> : null}</div>
    </div>
    {firstRun ? <FirstRun onClose={() => setFirstRun(null)} /> : null}
  </div>;
}
