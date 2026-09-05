/**
 * The page against a stubbed transport.
 *
 * The fetch boundary is stubbed, not the components: everything below the
 * network call is the real page, the real filtering and the real cards. That
 * is the difference between testing a frontend and testing a mock.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Feed } from "../api/types";
import { DiscoverPage, applyVote } from "./DiscoverPage";

const CARD = {
  secondary_title: null,
  alternative_titles: [],
  personal_match_text: "",
  personal_match_available: true,
  mal_score_text: "",
  genres_text: "",
  studios_text: "",
  episodes_text: "12 episodes",
  status: "Finished Airing",
  year_text: "2006",
  start_date: "",
  end_date: "",
  aired_text: null,
  synopsis: "",
  contributing_genres: [],
  cover_url: null,
  large_cover_url: null,
  mal_url: null,
  media_type: "tv",
  rank: 1,
};

const FEED: Feed = {
  source: "sample",
  ephemeral: true,
  profile: null,
  state_profile_id: null,
  hidden_count: 0,
  user_stats: {},
  catalogue: {
    genres: ["Psychological", "Comedy"],
    studios: ["Madhouse"],
    years: [2006, 2011],
    statuses: ["Finished Airing"],
  },
  state: {
    hidden_mal_ids: [],
    watch_later_mal_ids: [],
    liked_mal_ids: [],
    disliked_mal_ids: [],
    show_hidden: false,
  },
  recommendations: [
    {
      ...CARD,
      mal_id: 1535,
      display_title: "Death Note",
      personal_match: 92.4,
      mal_score: 8.62,
      genres: ["Psychological", "Supernatural"],
      studios: ["Madhouse"],
      episodes: 37,
      year: 2006,
      reason: "Matches your interests in Psychological.",
      genre_contributions: [
        { label: "Psychological", value: 76.1 },
        { label: "Community rating", value: 16.3 },
      ],
    },
    {
      ...CARD,
      mal_id: 9253,
      rank: 2,
      display_title: "Steins;Gate",
      personal_match: 88.1,
      mal_score: 9.07,
      genres: ["Comedy"],
      studios: ["White Fox"],
      episodes: 24,
      year: 2011,
      reason: "Matches your interests in Comedy.",
      genre_contributions: [{ label: "Comedy", value: 88.1 }],
    },
  ],
};

function stubFetch(feed: Feed = FEED) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/api/discover/feed")) {
      return new Response(JSON.stringify(feed), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response("{}", { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("DiscoverPage", () => {
  it("renders a skeleton before the feed arrives, then the cards", async () => {
    stubFetch();
    const { container } = render(<DiscoverPage />);
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
    expect(await screen.findByText("Death Note")).toBeInTheDocument();
    expect(screen.getByText("Steins;Gate")).toBeInTheDocument();
    expect(container.querySelectorAll(".skeleton")).toHaveLength(0);
  });

  it("says so when the feed is demonstration data rather than real", async () => {
    stubFetch();
    render(<DiscoverPage />);
    expect(await screen.findByText("Sample data")).toBeInTheDocument();
  });

  it("filters the feed from a genre pill without another request", async () => {
    const fetchMock = stubFetch();
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await screen.findByText("Death Note");
    const callsBefore = fetchMock.mock.calls.length;

    await user.click(screen.getByRole("button", { name: "Comedy" }));

    await waitFor(() => expect(screen.queryByText("Death Note")).not.toBeInTheDocument());
    expect(screen.getByText("Steins;Gate")).toBeInTheDocument();
    expect(fetchMock.mock.calls.length).toBe(callsBefore);
  });

  it("offers a way out of an empty result rather than a dead end", async () => {
    const user = userEvent.setup();
    stubFetch();
    render(<DiscoverPage />);
    await screen.findByText("Death Note");

    await user.click(screen.getByRole("button", { name: "Comedy" }));
    await user.click(screen.getByRole("button", { name: "Madhouse" }));

    expect(await screen.findByText("No titles match these filters")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(await screen.findByText("Death Note")).toBeInTheDocument();
  });

  it("re-sorts without refetching", async () => {
    const user = userEvent.setup();
    stubFetch();
    const { container } = render(<DiscoverPage />);
    await screen.findByText("Death Note");

    await user.click(screen.getByRole("button", { name: "MAL" }));
    await waitFor(() => {
      const titles = [...container.querySelectorAll(".card-title")].map((n) => n.textContent);
      expect(titles).toEqual(["Steins;Gate", "Death Note"]);
    });
  });

  it("records a vote in memory when the feed has nowhere to persist it", async () => {
    const fetchMock = stubFetch();
    const user = userEvent.setup();
    const { container } = render(<DiscoverPage />);
    await screen.findByText("Death Note");
    const callsBefore = fetchMock.mock.calls.length;

    const card = container.querySelector<HTMLElement>(".card")!;
    await user.click(within(card).getByRole("button", { name: "Like" }));

    expect(await within(card).findByRole("button", { name: "Liked" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // Ephemeral: no write was attempted.
    expect(fetchMock.mock.calls.length).toBe(callsBefore);
  });

  it("disables generation when there is no profile to generate for", async () => {
    stubFetch();
    render(<DiscoverPage />);
    expect(await screen.findByRole("button", { name: "Recommend 5 more" })).toBeDisabled();
  });

  it("shows the backend's own error model and a retry only when retryable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "network_error",
              title: "AniRec could not reach MyAnimeList",
              description: "The request timed out.",
              solution: "Check the connection and try again.",
              retryable: true,
            },
          }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(<DiscoverPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "AniRec could not reach MyAnimeList",
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

describe("applyVote", () => {
  const base = {
    hidden_mal_ids: [],
    watch_later_mal_ids: [],
    liked_mal_ids: [],
    disliked_mal_ids: [7],
    show_hidden: false,
  };

  it("makes sentiment mutually exclusive, as the service does", () => {
    const next = applyVote(base, 7, "sentiment", true);
    expect(next.liked_mal_ids).toEqual([7]);
    expect(next.disliked_mal_ids).toEqual([]);
  });

  it("adds and removes without duplicating", () => {
    const once = applyVote(base, 3, "watch_later", true);
    const twice = applyVote(once, 3, "watch_later", true);
    expect(twice.watch_later_mal_ids).toEqual([3]);
    expect(applyVote(twice, 3, "watch_later", false).watch_later_mal_ids).toEqual([]);
  });
});
