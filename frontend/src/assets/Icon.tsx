/**
 * The desktop's interface glyphs, drawn in the current text colour.
 *
 * The SVGs are copies of `AniRec/gui/resources/icons/ui/*.svg`, so the web
 * client draws the same marks. They are applied as a CSS mask rather than an
 * <img>, which is how `themed_ui_icon` tints them on the desktop: the colour
 * comes from the control's role, not from the file. Every glyph is decorative;
 * the control it sits in carries the accessible name.
 */

const url = (path: string) => new URL(path, import.meta.url).href;

export const ICONS = {
  "watch-later": url("./icons/watch-later.svg"),
  "watch-later-active": url("./icons/watch-later-active.svg"),
  "not-interested": url("./icons/not-interested.svg"),
  "not-interested-active": url("./icons/not-interested-active.svg"),
  "details-inspector": url("./icons/details-inspector.svg"),
  "external-mal": url("./icons/external-mal.svg"),
  "view-grid": url("./icons/view-grid.svg"),
  "view-grid-active": url("./icons/view-grid-active.svg"),
  "view-list": url("./icons/view-list.svg"),
  "view-list-active": url("./icons/view-list-active.svg"),
  "view-table": url("./icons/view-table.svg"),
  "view-table-active": url("./icons/view-table-active.svg"),
  filter: url("./icons/filter.svg"),
  refresh: url("./icons/refresh.svg"),
  "folder-watch-later": url("./icons/folder-watch-later.svg"),
  "folder-not-interested": url("./icons/folder-not-interested.svg"),
  search: url("./icons/search.svg"),
  "chevron-left": url("./icons/chevron-left.svg"),
  "chevron-right": url("./icons/chevron-right.svg"),
  "nav-discover": url("./shell/nav-discover.svg"),
  "nav-library": url("./shell/nav-library.svg"),
  profile: url("./shell/profile.svg"),
  "nav-compare": url("./shell/nav-compare.svg"),
  "nav-settings": url("./shell/nav-settings.svg"),
  "fact-bias": url("./shell/fact-bias.svg"),
  "fact-completion": url("./shell/fact-completion.svg"),
  "fact-contrarian": url("./shell/fact-contrarian.svg"),
  "fact-divisive": url("./shell/fact-divisive.svg"),
  "fact-era": url("./shell/fact-era.svg"),
  "fact-gem": url("./shell/fact-gem.svg"),
  "fact-hype": url("./shell/fact-hype.svg"),
  "fact-mainstream": url("./shell/fact-mainstream.svg"),
  "fact-nemesis": url("./shell/fact-nemesis.svg"),
  "fact-rewatch": url("./shell/fact-rewatch.svg"),
  "fact-season-fall": url("./shell/fact-season-fall.svg"),
  "fact-season-spring": url("./shell/fact-season-spring.svg"),
  "fact-season-summer": url("./shell/fact-season-summer.svg"),
  "fact-season-winter": url("./shell/fact-season-winter.svg"),
  "fact-sync": url("./shell/fact-sync.svg"),
  "fact-trusted": url("./shell/fact-trusted.svg"),
  "fact-unknown": url("./shell/fact-unknown.svg"),
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  const mask = `url("${ICONS[name]}")`;
  return <span className={`ui-icon ${className}`.trim()} data-icon={name} aria-hidden="true"
    style={{ maskImage: mask, WebkitMaskImage: mask }} />;
}
