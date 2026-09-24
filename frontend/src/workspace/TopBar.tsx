/**
 * The top bar (D-019): the layout people already know from the sites they
 * use every day. The name on the left goes home; the pages are tabs; the
 * bell and the picture sit top right, and the picture opens the menu that
 * holds your profile and settings, which is where a newcomer looks for them.
 *
 * Both menus are disclosures (a button that shows a panel), not ARIA menus:
 * Tab moves through them like any other links, Escape closes them and puts
 * focus back on the button, and a click elsewhere closes them.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Feed, SystemState } from "../api/types";
import { Icon, type IconName } from "../assets/Icon";
import type { Notice } from "./Shell";

export const TABS: readonly [id: "discover" | "library" | "compare", label: string, icon: IconName][] = [
  ["discover", "Discover", "nav-discover"],
  ["library", "My Library", "nav-library"],
  ["compare", "Compare", "nav-compare"],
];

/** A button and the panel it opens; closes on Escape, outside click and navigation. */
function Popover({ label, button, className, children }: {
  label: string;
  button: (props: { "aria-expanded": boolean; "aria-controls": string; onClick: () => void; ref: React.Ref<HTMLButtonElement> }) => ReactNode;
  className: string;
  children: (close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    const navigate = () => setOpen(false);
    document.addEventListener("mousedown", outside);
    document.addEventListener("keydown", escape);
    window.addEventListener("hashchange", navigate);
    return () => {
      document.removeEventListener("mousedown", outside);
      document.removeEventListener("keydown", escape);
      window.removeEventListener("hashchange", navigate);
    };
  }, [open]);
  return <div className={`popover ${className}`} ref={root}>
    {button({ "aria-expanded": open, "aria-controls": id, onClick: () => setOpen((value) => !value), ref: trigger })}
    <div id={id} className="popover-panel" role="region" aria-label={label} hidden={!open}>{open ? children(() => setOpen(false)) : null}</div>
  </div>;
}

const ago = (at: Date, now: Date) => {
  const minutes = Math.floor((now.getTime() - at.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  return at.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
};

export function Notifications({ notices }: { notices: Notice[] }) {
  // Everything up to the newest notification is read once the panel opens.
  const [readUpTo, setReadUpTo] = useState(-1);
  const unread = notices.filter((notice) => notice.id > readUpTo).length;
  const newest = notices.at(-1)?.id ?? -1;
  return <Popover label="Notifications" className="notifications"
    button={(props) => <button type="button" className="icon-button" {...props}
      aria-label={unread ? `Notifications, ${unread} new` : "Notifications"}
      onClick={() => { props.onClick(); setReadUpTo(newest); }}>
      <BellIcon />{unread ? <span className="badge" aria-hidden="true">{unread > 9 ? "9+" : unread}</span> : null}
    </button>}>
    {() => <>
      <h2 className="popover-title">Notifications</h2>
      {notices.length ? <ul className="notice-list">
        {[...notices].reverse().map((notice) => <li key={notice.id} data-tone={notice.tone}>
          <p className="notice-title">{notice.title}</p>
          {notice.detail ? <p className="notice-detail">{notice.detail}</p> : null}
          <p className="notice-time">{ago(notice.at, new Date())}</p>
        </li>)}
      </ul> : <p className="notice-empty">You're all caught up.</p>}
    </>}
  </Popover>;
}

/** The reader's MyAnimeList picture when the profile has one, otherwise initials. */
export function useAvatar(system: SystemState | null): string | null {
  const [url, setUrl] = useState<string | null>(null);
  const profileId = system?.profile?.profile_id ?? null;
  useEffect(() => {
    setUrl(null);
    if (!profileId) return;
    let cancelled = false;
    api.profile(false).then((read) => {
      const avatar = read.profile?.identity?.avatar_url;
      if (!cancelled && avatar && /^https:\/\//i.test(avatar)) setUrl(avatar);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [profileId]);
  return url;
}

/** What the account menu can ask the workspace to do (D-021). */
export type AccountAction = "register" | "sign-in" | "sign-out";

export function Account({ system, feed, avatarUrl, onSetUp, onAccount }: {
  system: SystemState | null; feed: Feed | null; avatarUrl: string | null;
  onSetUp?: () => void; onAccount?: (action: AccountAction) => void;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  const account = system?.account ?? null;
  const registered = account?.kind === "registered";
  const name = system?.profile?.username ?? null;
  const letters = name ? name.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2).toLocaleUpperCase() : null;
  const context = registered ? account?.email ?? "Signed in"
    : feed?.source === "sample" ? "Exploring the sample library"
      : name ? "Guest: create an account to keep your list" : "No profile yet";
  const picture = avatarUrl && failed !== avatarUrl
    ? <img src={avatarUrl} alt="" referrerPolicy="no-referrer" onError={() => setFailed(avatarUrl)} />
    : letters ? <span aria-hidden="true">{letters}</span> : <PersonIcon />;
  return <Popover label="Account" className="account"
    button={(props) => <button type="button" className="avatar-button" {...props}
      aria-label={name ? `Account menu for ${name}` : "Account menu"}>{picture}</button>}>
    {(close) => <>
      <div className="account-head">
        <span className="avatar-large" aria-hidden="true">{picture}</span>
        <div><p className="account-name">{name ?? (registered ? "Your account" : "Guest")}</p><p className="account-context">{context}</p></div>
      </div>
      <ul className="account-links">
        {!registered && onAccount ? <>
          <li><button type="button" onClick={() => { close(); onAccount("register"); }}><Icon name="profile" />Create account</button></li>
          <li><button type="button" onClick={() => { close(); onAccount("sign-in"); }}><Icon name="profile" />Sign in</button></li>
        </> : null}
        {!name && onSetUp ? <li><button type="button" onClick={() => { close(); onSetUp(); }}><Icon name="nav-library" />Set up your profile</button></li> : null}
        <li><a href="#/profile" onClick={close}><Icon name="profile" />Your profile</a></li>
        <li><a href="#/settings" onClick={close}><Icon name="nav-settings" />Settings</a></li>
        {registered && onAccount ? <li><button type="button" onClick={() => { close(); onAccount("sign-out"); }}>Sign out</button></li> : null}
      </ul>
    </>}
  </Popover>;
}

function BellIcon() {
  return <svg className="bell" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
    <path d="M12 3a6 6 0 0 0-6 6v4l-2 3h16l-2-3V9a6 6 0 0 0-6-6zM9.5 19a2.5 2.5 0 0 0 5 0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
  </svg>;
}

function PersonIcon() {
  return <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
    <circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" strokeWidth="2" />
    <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" fill="none" stroke="currentColor" strokeWidth="2" />
  </svg>;
}

export function TopBar({ page, system, feed, notices, avatarUrl, onSetUp, onAccount }: {
  page: string; system: SystemState | null; feed: Feed | null; notices: Notice[]; avatarUrl: string | null;
  onSetUp?: () => void; onAccount?: (action: AccountAction) => void;
}) {
  return <header className="topbar">
    <a className="brand" href="#/discover" aria-label="AniRec home">AniRec</a>
    <nav className="tabs" aria-label="Main navigation">
      {TABS.map(([id, label, icon]) => <a key={id} href={`#/${id}`} aria-current={page === id ? "page" : undefined}>
        <Icon name={icon} className="tab-icon" /><span>{label}</span>
      </a>)}
    </nav>
    <div className="topbar-end">
      <Notifications notices={notices} />
      <Account system={system} feed={feed} avatarUrl={avatarUrl} onSetUp={onSetUp} onAccount={onAccount} />
    </div>
  </header>;
}
