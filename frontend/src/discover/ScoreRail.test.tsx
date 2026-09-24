import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Explanation, RecommendationViewModel } from "../api/types";
import { fitRankText, rankingEngineLabel, WhyExplanation } from "./ScoreRail";

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

const ADDITIVE: Explanation = {
  schema_version: 1,
  method: "exact-additive",
  unit: "ranking-score",
  baseline: 0,
  total: 2.25,
  full_score: 2.25,
  full_rank: 4,
  ranked_candidate_count: 13_458,
  unavailable_reason: null,
  influences: [],
  segments: [
    {
      kind: "taste",
      label: "Psychological",
      facet: "genre",
      value: 3.5,
      member_count: null,
      rank_without: null,
      signal_available: true,
      feedback_adjustment: 0.25,
      taste: { affinity: 0.8, rarity: 1.1, rated_count: 2, mean_user_score: 9, overall_mean_user_score: 7.4 },
      community: null,
      evidence: [{ mal_id: 19, title: "Monster", user_score: 10, list_status: null, value: null, rank_without: null }],
    },
    {
      kind: "community",
      label: "Community rating",
      facet: null,
      value: -1.25,
      member_count: null,
      rank_without: null,
      signal_available: false,
      feedback_adjustment: null,
      taste: null,
      community: { mean_score: null, scoring_users: null },
      evidence: [],
    },
  ],
};

const COUNTERFACTUAL: Explanation = {
  schema_version: 1,
  method: "counterfactual-removal",
  unit: "model-score",
  baseline: null,
  total: null,
  full_score: 0.8,
  full_rank: 4,
  ranked_candidate_count: 13_458,
  history_window: 2,
  unavailable_reason: null,
  segments: [{
    kind: "history-group",
    label: "Psychological",
    facet: "genre",
    value: -0.3,
    member_count: 2,
    rank_without: 2,
    signal_available: true,
    feedback_adjustment: null,
    taste: null,
    community: null,
    evidence: [
      { mal_id: 19, title: "Monster", user_score: 10, list_status: "completed", value: 0.7, rank_without: 33 },
      { mal_id: 437, title: "Perfect Blue", user_score: 9, list_status: "completed", value: 0.2, rank_without: 8 },
    ],
  }],
  influences: [{ mal_id: 19, title: "Monster", user_score: 10, list_status: "completed", value: 0.7, rank_without: 33 }],
};

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

describe("why explanation", () => {
  it("keeps additive negative terms, gives the bar a numeric text equivalent, and exposes rated evidence", async () => {
    const user = userEvent.setup();
    render(<WhyExplanation why={ADDITIVE} />);
    expect(screen.getByText("Ranking score").nextSibling).toHaveTextContent("2.25");
    expect(screen.getByRole("img", { name: /Genre · Psychological \+3.5, raised it.*Community rating -1.25, held it back/ })).toBeInTheDocument();
    const segment = screen.getByText("Genre · Psychological").closest("details")!;
    await user.click(within(segment).getByText("Genre · Psychological"));
    expect(within(segment).getByText(/2 rated titles/)).toHaveTextContent("average 9 / 10");
    expect(within(segment).getByText(/adjusted by your likes\/dislikes/i)).toHaveTextContent("+0.25");
    expect(within(segment).getByText("Monster").parentElement).toHaveTextContent("10 / 10");
    const community = screen.getByText("Community rating").closest("details")!;
    await user.click(within(community).getByText("Community rating"));
    expect(within(community).getByText(/not about your taste/i)).toBeInTheDocument();
    expect(within(community).getByText(/neutral stand-in/i)).toBeInTheDocument();
  });

  it("renders unknown taste counts and means as unknown, never zero", async () => {
    const user = userEvent.setup();
    const taste = ADDITIVE.segments[0]!;
    render(<WhyExplanation why={{ ...ADDITIVE, segments: [{
      ...taste,
      feedback_adjustment: null,
      taste: { ...taste.taste!, rated_count: null, mean_user_score: null, overall_mean_user_score: null },
      evidence: [],
    }] }} />);
    await user.click(screen.getByText("Genre · Psychological"));
    expect(screen.getByText("Rated-title count and mean rating: unknown.")).toBeInTheDocument();
    expect(screen.getByText("Overall mean rating: unknown.")).toBeInTheDocument();
    expect(screen.queryByText(/0 rated titles/)).not.toBeInTheDocument();
  });

  it("describes sequence effects as removals from the recent history window, not genre inputs or shares", async () => {
    const user = userEvent.setup();
    render(<WhyExplanation why={COUNTERFACTUAL} />);
    expect(screen.getByText(/your 2 most recent titles/i)).toBeInTheDocument();
    const segment = screen.getByText("Your Psychological titles").closest("details")!;
    expect(segment).toHaveTextContent("#4 → #2");
    expect(segment).toHaveTextContent("-0.3 · Held it back");
    await user.click(within(segment).getByText("Your Psychological titles"));
    expect(within(segment).getByText(/removing it leaves no history/i)).toHaveTextContent("brand-new reader's rank");
    expect(within(segment).getByText("Monster").parentElement).toHaveTextContent("+0.7 · raised it");
    expect(screen.getByText(/Because you watched Monster/).closest("li")).toHaveTextContent("#4 → #33 · effect +0.7 · raised it");
    expect(screen.queryByText(/because it is Psychological/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it.each([
    ["engine-cannot-explain", "this engine can't explain its picks"],
    ["explanation-failed", "couldn't compute an explanation this time"],
    ["explanation-unavailable", "couldn't compute an explanation this time"],
    ["outside-ranked-candidates", "not in the ranked set"],
    ["score-parts-missing", "no score breakdown was recorded"],
  ])("maps unavailable reason %s to plain text", (reason, copy) => {
    render(<WhyExplanation why={{ ...ADDITIVE, method: "unavailable", total: null, baseline: null, segments: [], unavailable_reason: reason }} />);
    expect(screen.getByText("This pick can't be explained")).toBeInTheDocument();
    expect(screen.getByText(copy)).toBeInTheDocument();
  });

  it("treats a null explanation as unavailable without borrowing legacy reason copy", () => {
    render(<WhyExplanation why={null} />);
    expect(screen.getByText("This pick can't be explained")).toBeInTheDocument();
    expect(screen.getByText("No explanation was recorded for this pick.")).toBeInTheDocument();
  });
});
