import { useEffect, useState } from "react";
import { EMPTY_FILTERS, type Filters, type SortMode } from "./filtering";
import type { ViewMode } from "./FeedViews";

export interface DiscoverLocation {
  filters: Filters;
  sort: SortMode;
  page: number;
  view: ViewMode;
  showHidden: boolean;
  hiddenSpecified: boolean;
}

const sorts: SortMode[] = ["personal-match", "mal-score", "year", "title"];
const views: ViewMode[] = ["cards", "list", "table"];
const list = (params: URLSearchParams, key: string) => [...new Set(params.getAll(key).map((value) => value.trim()).filter(Boolean))];
const number = (value: string | null, min: number, max: number): number | null => {
  if (value === null || !/^\d+(?:\.\d+)?$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max ? parsed : null;
};

export function readDiscoverLocation(hash = window.location.hash): DiscoverLocation {
  const params = new URLSearchParams(hash.startsWith("#/discover?") ? hash.slice("#/discover?".length) : "");
  const sort = params.get("sort") as SortMode;
  const view = params.get("view") as ViewMode;
  const score = number(params.get("minScore"), 0, 10);
  return {
    filters: {
      genres: list(params, "genre"), studios: list(params, "studio"),
      years: list(params, "year").map((value) => number(value, 1900, 2100)).filter((value): value is number => value !== null),
      minimumMalScore: score !== null && score % 0.5 === 0 ? score : null,
      status: params.get("status") || null,
      minimumEpisodes: number(params.get("minEpisodes"), 0, 100000),
      maximumEpisodes: number(params.get("maxEpisodes"), 0, 100000),
    },
    sort: sorts.includes(sort) ? sort : "personal-match",
    page: Math.max(0, (number(params.get("page"), 1, 100000) ?? 1) - 1),
    view: views.includes(view) ? view : "cards",
    showHidden: params.get("hidden") === "show",
    hiddenSpecified: params.has("hidden"),
  };
}

export function discoverHref(state: DiscoverLocation): string {
  const params = new URLSearchParams();
  state.filters.genres.forEach((value) => params.append("genre", value));
  state.filters.studios.forEach((value) => params.append("studio", value));
  state.filters.years.forEach((value) => params.append("year", String(value)));
  if (state.filters.minimumMalScore !== null) params.set("minScore", String(state.filters.minimumMalScore));
  if (state.filters.status) params.set("status", state.filters.status);
  if (state.filters.minimumEpisodes !== null) params.set("minEpisodes", String(state.filters.minimumEpisodes));
  if (state.filters.maximumEpisodes !== null) params.set("maxEpisodes", String(state.filters.maximumEpisodes));
  if (state.sort !== "personal-match") params.set("sort", state.sort);
  if (state.page > 0) params.set("page", String(state.page + 1));
  if (state.view !== "cards") params.set("view", state.view);
  if (state.showHidden) params.set("hidden", "show");
  else if (state.hiddenSpecified) params.set("hidden", "hide");
  return `#/discover${params.size ? `?${params}` : ""}`;
}

export function chipHref(kind: "genre" | "studio", value: string, current = readDiscoverLocation()): string {
  return discoverHref({ ...current, page: 0, filters: {
    ...EMPTY_FILTERS, ...current.filters,
    [kind === "genre" ? "genres" : "studios"]: [value],
  } });
}

export function useDiscoverLocation() {
  const [state, setState] = useState(readDiscoverLocation);
  useEffect(() => {
    const read = () => { if (window.location.hash.startsWith("#/discover")) setState(readDiscoverLocation()); };
    window.addEventListener("hashchange", read);
    window.addEventListener("popstate", read);
    return () => { window.removeEventListener("hashchange", read); window.removeEventListener("popstate", read); };
  }, []);
  const update = (change: Partial<DiscoverLocation>, replace = false) => {
    const next = { ...state, ...change };
    setState(next);
    const href = discoverHref(next);
    if (window.location.hash !== href) window.history[replace ? "replaceState" : "pushState"](null, "", href);
  };
  return [state, update] as const;
}
