import type { RecommendationViewModel } from "../api/types";
import { usePlatform } from "../platform/PlatformContext";
import { chipHref, readDiscoverLocation } from "./discoverUrl";

/** Optional public metadata can appear before its generated API contract catches up. */
type PublicMedia = RecommendationViewModel & {
  anidb_url?: string | null;
  anilist_url?: string | null;
  pv_youtube_url?: string | null;
};

export function pvEmbedUrl(model: PublicMedia): string | null {
  const raw = model.pv_youtube_url;
  if (!raw) return null;
  try {
    const url = new URL(raw);
    const host = url.hostname.toLowerCase();
    const id = host === "youtu.be" ? url.pathname.slice(1) :
      host === "youtube.com" || host === "www.youtube.com" ? (url.pathname === "/watch" ? url.searchParams.get("v") : url.pathname.startsWith("/embed/") ? url.pathname.slice(7) : null) : null;
    return id && /^[\w-]{11}$/.test(id) ? `https://www.youtube-nocookie.com/embed/${id}?autoplay=1` : null;
  } catch { return null; }
}

/** YouTube's preview for the same validated video used by the player. */
export function pvThumbnailUrl(model: PublicMedia): string | null {
  const embed = pvEmbedUrl(model);
  if (!embed) return null;
  const id = new URL(embed).pathname.split("/").pop();
  return `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;
}

export function ExternalLinks({ model, onExternal, labelled = false }: {
  model: PublicMedia;
  onExternal?: (model: RecommendationViewModel) => void;
  labelled?: boolean;
}) {
  const platform = usePlatform();
  const official = (raw: string | null | undefined, host: string) => {
    if (!raw) return null;
    try {
      const url = new URL(raw);
      return url.protocol === "https:" && (url.hostname === host || url.hostname === `www.${host}`) ? url.href : null;
    } catch { return null; }
  };
  const links = [
    ["MAL", official(model.mal_url, "myanimelist.net")],
    ["AniDB", official(model.anidb_url, "anidb.net")],
    ["AniList", official(model.anilist_url, "anilist.co")],
  ].filter((entry): entry is [string, string] => typeof entry[1] === "string");
  if (!links.length) return null;
  return <div className="external-links" aria-label="Anime database links">
    {labelled ? <span className="lbl">LINKS</span> : null}
    <div className="external-links-row">{links.map(([name, url]) => <a key={name} href={url} target="_blank" rel="noreferrer noopener"
      aria-label={`Open ${model.display_title} on ${name === "MAL" ? "MyAnimeList" : name} (external)`}
      onClick={(event) => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
        event.preventDefault();
        void platform.openExternal(url).then(() => onExternal?.(model)).catch(() => {});
      }}>{name} <span aria-hidden="true">↗</span></a>)}</div>
  </div>;
}

export function MetadataChips({ model, onNavigate, compact = false }: { model: RecommendationViewModel; onNavigate?: () => void; compact?: boolean }) {
  const current = readDiscoverLocation();
  const navigate = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
    onNavigate?.();
  };
  const studio = model.studios[0];
  const available = 5 - (studio ? 1 : 0);
  const overflowing = model.studios.length > 1 || model.genres.length > available;
  const shownGenres = compact ? model.genres.slice(0, overflowing ? available - 1 : available) : model.genres;
  const shownStudios = compact ? model.studios.slice(0, 1) : model.studios;
  const more = [...model.studios.slice(shownStudios.length), ...model.genres.slice(shownGenres.length)];
  return <div className={compact ? "card-tags metadata-chips" : "metadata-chips"} title={compact ? [...model.studios, ...model.genres].join(" · ") : undefined}>
    {shownStudios.map((studio) => <a key={`studio:${studio}`} className="card-tag studio" href={chipHref("studio", studio, current)} onClick={navigate}
      aria-label={`Explore studio ${studio}`}><span className="visually-hidden">Studio: </span>{studio}</a>)}
    {shownGenres.map((genre) => <a key={`genre:${genre}`} className="card-tag" href={chipHref("genre", genre, current)} onClick={navigate}
      aria-label={`Explore genre ${genre}`}><span className="visually-hidden">Genre: </span>{genre}</a>)}
    {compact && more.length ? <span className="card-tag more" title={more.join(" · ")}>+{more.length}<span className="visually-hidden"> more: {more.join(", ")}</span></span> : null}
  </div>;
}
