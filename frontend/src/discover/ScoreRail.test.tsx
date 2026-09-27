import { describe, expect, it } from "vitest";
import type { RecommendationViewModel } from "../api/types";
import { fitRankText, rankingEngineLabel } from "./ScoreRail";

function model(overrides: Partial<RecommendationViewModel> = {}): RecommendationViewModel {
  return {
    mal_id: 1,
    rank: 1,
    display_title: "Perfect Blue",
    secondary_title: null,
    alternative_titles: [],
    personal_match: 0,
    personal_match_text: "",
    personal_match_available: false,
    mal_score: 8.55,
    mal_score_text: "",
    genres: ["Psychological"],
    genres_text: "Psychological",
    studios: ["Madhouse"],
    studios_text: "Madhouse",
    episodes: 1,
    episodes_text: "1 episode",
    status: "Finished Airing",
    year: 1998,
    year_text: "1998",
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
    media_type: "movie",
    fit_rank: 4,
    fit_pool_size: 13_458,
    fit_top_percent: 0.0297,
    ranking_id: "ranking-a",
    why: null,
    ...overrides,
  };
}

describe("personal fit line", () => {
  it("states the API rank and pool in the desktop's words, never as a percentage", () => {
    const text = fitRankText(model());
    expect(text).toBe("Ranked #4 of 13,458 for you");
    expect(text).not.toContain("%");
    expect(rankingEngineLabel("sasrec-onnx")).toBe("sequence model");
  });

  it("uses words, not zero or a dash, when the rank or the pool is missing", () => {
    expect(fitRankText(model({ fit_rank: null, fit_pool_size: null, fit_top_percent: null }))).toBe("Personal match unavailable");
    expect(fitRankText(model({ fit_pool_size: null }))).toBe("Personal match unavailable");
  });
});
