/**
 * The filter and sort rules, asserted against the same cases the Python side
 * cares about. If these two implementations ever disagree, a title filtered
 * out on the desktop appears on the web, which is the failure this file
 * exists to catch.
 */

import { describe, expect, it } from "vitest";
import type { RecommendationViewModel } from "../api/types";
import { EMPTY_FILTERS, activeFilterCount, filterAndSort, isActive } from "./filtering";

function model(overrides: Partial<RecommendationViewModel>): RecommendationViewModel {
  return {
    mal_id: 1,
    rank: 1,
    display_title: "Untitled",
    secondary_title: null,
    alternative_titles: [],
    personal_match: 50,
    personal_match_text: "",
    personal_match_available: true,
    mal_score: 7,
    mal_score_text: "",
    genres: [],
    genres_text: "",
    studios: [],
    studios_text: "",
    episodes: 12,
    episodes_text: "",
    status: "Finished Airing",
    year: 2010,
    year_text: "",
    start_date: "",
    end_date: "",
    aired_text: null,
    synopsis: "",
    reason: "",
    contributing_genres: [],
    genre_contributions: [],
    cover_url: null,
    large_cover_url: null,
    mal_url: null,
    media_type: "tv",
    ...overrides,
  };
}

describe("filterAndSort", () => {
  it("treats values within one kind as an or", () => {
    const models = [
      model({ mal_id: 1, genres: ["Action"] }),
      model({ mal_id: 2, genres: ["Comedy"] }),
      model({ mal_id: 3, genres: ["Drama"] }),
    ];
    const result = filterAndSort(
      models,
      { ...EMPTY_FILTERS, genres: ["Action", "Comedy"] },
      "personal-match",
    );
    expect(result.map((item) => item.mal_id)).toEqual([1, 2]);
  });

  it("treats different kinds as an and", () => {
    const models = [
      model({ mal_id: 1, genres: ["Action"], studios: ["Madhouse"] }),
      model({ mal_id: 2, genres: ["Action"], studios: ["Bones"] }),
    ];
    const result = filterAndSort(
      models,
      { ...EMPTY_FILTERS, genres: ["Action"], studios: ["Madhouse"] },
      "personal-match",
    );
    expect(result.map((item) => item.mal_id)).toEqual([1]);
  });

  it("matches case-insensitively, so a clicked genre and a typed one are one filter", () => {
    const models = [model({ mal_id: 1, studios: ["Shaft"] })];
    const result = filterAndSort(
      models,
      { ...EMPTY_FILTERS, studios: ["shaft"] },
      "personal-match",
    );
    expect(result).toHaveLength(1);
  });

  it("excludes a title with no score when a score floor is set", () => {
    const models = [
      model({ mal_id: 1, mal_score: null }),
      model({ mal_id: 2, mal_score: 8 }),
    ];
    const result = filterAndSort(
      models,
      { ...EMPTY_FILTERS, minimumMalScore: 7 },
      "personal-match",
    );
    expect(result.map((item) => item.mal_id)).toEqual([2]);
  });

  it("sorts missing values last rather than as zero", () => {
    const models = [
      model({ mal_id: 1, mal_score: null }),
      model({ mal_id: 2, mal_score: 4.2 }),
      model({ mal_id: 3, mal_score: 9.1 }),
    ];
    const result = filterAndSort(models, EMPTY_FILTERS, "mal-score");
    expect(result.map((item) => item.mal_id)).toEqual([3, 2, 1]);
  });

  it("sorts an unavailable personal match last", () => {
    const models = [
      model({ mal_id: 1, personal_match: 0, personal_match_available: false }),
      model({ mal_id: 2, personal_match: 12 }),
    ];
    const result = filterAndSort(models, EMPTY_FILTERS, "personal-match");
    expect(result.map((item) => item.mal_id)).toEqual([2, 1]);
  });

  it("does not mutate the input array", () => {
    const models = [model({ mal_id: 1, personal_match: 10 }), model({ mal_id: 2, personal_match: 90 })];
    const before = models.map((item) => item.mal_id);
    filterAndSort(models, EMPTY_FILTERS, "personal-match");
    expect(models.map((item) => item.mal_id)).toEqual(before);
  });
});

describe("filter state", () => {
  it("reports inactive when nothing is set", () => {
    expect(isActive(EMPTY_FILTERS)).toBe(false);
    expect(activeFilterCount(EMPTY_FILTERS)).toBe(0);
  });

  it("counts an episode band as one filter, not two", () => {
    const filters = { ...EMPTY_FILTERS, minimumEpisodes: 12, maximumEpisodes: 26 };
    expect(activeFilterCount(filters)).toBe(1);
  });
});
