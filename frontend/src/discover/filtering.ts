/**
 * A direct port of `filter_and_sort_recommendations`
 * (AniRec/gui/recommendation_page.py:142).
 *
 * Kept identical on purpose, including the rules that are easy to get subtly
 * wrong: within one kind the values are an OR, across kinds an AND, matching
 * is case-folded, and a missing value sorts last rather than as zero - a title
 * with no MAL score must not rank above one scored 4.2.
 *
 * It lives on the client because these are projections of a feed already in
 * memory; sending a request to re-filter fifty rows the browser is holding
 * would add a round trip to a keystroke. That stops being true at catalogue
 * scale, and the API takes the same filter vocabulary
 * (AniRec/presentation/filters.py) as query parameters when it does.
 */

import type { RecommendationViewModel } from "../api/types";

export type SortMode = "personal-match" | "mal-score" | "year" | "title";

export interface Filters {
  genres: string[];
  studios: string[];
  years: number[];
  minimumMalScore: number | null;
  status: string | null;
  minimumEpisodes: number | null;
  maximumEpisodes: number | null;
}

export const EMPTY_FILTERS: Filters = {
  genres: [],
  studios: [],
  years: [],
  minimumMalScore: null,
  status: null,
  minimumEpisodes: null,
  maximumEpisodes: null,
};

export function isActive(filters: Filters): boolean {
  return (
    filters.genres.length > 0 ||
    filters.studios.length > 0 ||
    filters.years.length > 0 ||
    filters.minimumMalScore !== null ||
    filters.status !== null ||
    filters.minimumEpisodes !== null ||
    filters.maximumEpisodes !== null
  );
}

export function activeFilterCount(filters: Filters): number {
  return (
    filters.genres.length +
    filters.studios.length +
    filters.years.length +
    (filters.minimumMalScore !== null ? 1 : 0) +
    (filters.status !== null ? 1 : 0) +
    (filters.minimumEpisodes !== null || filters.maximumEpisodes !== null ? 1 : 0)
  );
}

const fold = (value: string) => value.toLocaleLowerCase();

function intersects(wanted: string[], present: string[]): boolean {
  if (wanted.length === 0) return true;
  const haystack = new Set(present.map(fold));
  return wanted.some((item) => haystack.has(fold(item)));
}

export function filterAndSort(
  models: RecommendationViewModel[],
  filters: Filters,
  sortMode: SortMode,
): RecommendationViewModel[] {
  const status = filters.status ? fold(filters.status) : null;
  const years = new Set(filters.years);

  const filtered = models.filter((model) => {
    if (!intersects(filters.genres, model.genres)) return false;
    if (!intersects(filters.studios, model.studios)) return false;
    if (years.size > 0 && (model.year === null || !years.has(model.year))) return false;
    if (
      filters.minimumMalScore !== null &&
      (model.mal_score === null || model.mal_score < filters.minimumMalScore)
    ) {
      return false;
    }
    if (status !== null && fold(model.status) !== status) return false;
    if (
      filters.minimumEpisodes !== null &&
      (model.episodes === null || model.episodes < filters.minimumEpisodes)
    ) {
      return false;
    }
    if (
      filters.maximumEpisodes !== null &&
      (model.episodes === null || model.episodes > filters.maximumEpisodes)
    ) {
      return false;
    }
    return true;
  });

  if (sortMode === "personal-match") return sortPersonalFit(filtered);

  // Missing-last, then descending. Mirrors the Python tuple keys for the
  // remaining source fields exactly: `(not available, -value)`.
  const compare: Record<SortMode, (a: RecommendationViewModel, b: RecommendationViewModel) => number> =
    {
      "personal-match": () => 0,
      "mal-score": (a, b) =>
        rank(a.mal_score === null, b.mal_score === null) ||
        (b.mal_score ?? 0) - (a.mal_score ?? 0),
      year: (a, b) =>
        rank(a.year === null, b.year === null) || (b.year ?? 0) - (a.year ?? 0),
      title: (a, b) => fold(a.display_title).localeCompare(fold(b.display_title)),
    };

  return [...filtered].sort(compare[sortMode]);
}

/**
 * Fit ranks are comparable only inside one ranking snapshot. Sort each
 * ranking's existing slots independently, then append rows whose rank is
 * unavailable. This preserves cross-ranking order instead of silently
 * pretending that #4 from two different candidate pools means the same thing.
 */
function sortPersonalFit(models: RecommendationViewModel[]): RecommendationViewModel[] {
  const ranked = models.filter((model) => model.fit_rank !== null && model.fit_rank !== undefined);
  const unavailable = models.filter((model) => model.fit_rank === null || model.fit_rank === undefined);
  const groups = new Map<string, RecommendationViewModel[]>();

  ranked.forEach((model, index) => {
    const key = model.ranking_id ?? `missing-ranking-id:${index}`;
    groups.set(key, [...(groups.get(key) ?? []), model]);
  });
  for (const [key, items] of groups) {
    if (!key.startsWith("missing-ranking-id:")) {
      groups.set(key, [...items].sort((a, b) => a.fit_rank! - b.fit_rank!));
    }
  }

  const offsets = new Map<string, number>();
  const sorted = ranked.map((model, index) => {
    const key = model.ranking_id ?? `missing-ranking-id:${index}`;
    const offset = offsets.get(key) ?? 0;
    offsets.set(key, offset + 1);
    return groups.get(key)![offset]!;
  });
  return [...sorted, ...unavailable];
}

function rank(missingA: boolean, missingB: boolean): number {
  return Number(missingA) - Number(missingB);
}
