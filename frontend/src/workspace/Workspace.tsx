import { useEffect, useRef, useState } from "react";
import { DiscoverPage } from "../discover/DiscoverPage";
import { ProfilePage } from "./ProfilePage";
import { ComparePage } from "./ComparePage";
import { SettingsPage } from "./SettingsPage";
import "./workspace.css";

const pages = [
  ["discover", "Discover", new URL("../../../AniRec/gui/resources/icons/ui/nav-discover.svg", import.meta.url).href],
  ["library", "My Library", new URL("../../../AniRec/gui/resources/icons/ui/nav-library.svg", import.meta.url).href],
  ["profile", "Profile", new URL("../../../AniRec/gui/resources/icons/ui/profile.svg", import.meta.url).href],
  ["compare", "Compare", new URL("../../../AniRec/gui/resources/icons/ui/nav-compare.svg", import.meta.url).href],
  ["settings", "Settings", new URL("../../../AniRec/gui/resources/icons/ui/nav-settings.svg", import.meta.url).href],
] as const;
type Page = typeof pages[number][0];
const route = (): Page => pages.find(([id]) => location.hash === `#/${id}`)?.[0] ?? "discover";

export function Workspace() {
  const [page, setPage] = useState<Page>(route);
  const [visited, setVisited] = useState<Set<Page>>(() => new Set([route()]));
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
  return <div className="workspace">
    <a className="skip-link" href="#workspace-content">Skip to content</a>
    <aside className="workspace-nav"><div className="workspace-brand">ANIREC <small>アニレク</small></div>
      <nav aria-label="Main navigation">{pages.map(([id, label, icon], i) => <a href={`#/${id}`} key={id} aria-current={page === id ? "page" : undefined}>
        <span className="house-icon" aria-hidden="true" style={{ maskImage: `url("${icon}")` }} /><span className="nav-index" aria-hidden="true">0{i + 1}</span>{label}
      </a>)}</nav>
    </aside>
    <div className="workspace-content" ref={content} id="workspace-content" tabIndex={-1}>
      <DiscoverPage surface={page === "discover" || page === "library" ? page : "inactive"} />
      <div hidden={page !== "profile"}>{visited.has("profile") ? <ProfilePage /> : null}</div>
      <div hidden={page !== "compare"}>{visited.has("compare") ? <ComparePage /> : null}</div>
      <div hidden={page !== "settings"}>{visited.has("settings") ? <SettingsPage /> : null}</div>
    </div>
  </div>;
}
