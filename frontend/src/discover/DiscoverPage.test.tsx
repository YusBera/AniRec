/**
 * The page against a stubbed transport.
 *
 * The fetch boundary is stubbed, not the components: everything below the
 * network call is the real page, the real filtering and the real cards. That
 * is the difference between testing a frontend and testing a mock.
 */

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

beforeEach(() => {
  // jsdom has no native dialog lifecycle. The real focus trap and Escape are
  // verified in Chromium; this models asynchronous close events, including
  // the StrictMode cleanup/reopen sequence that previously dismissed it.
  vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(function (this: HTMLDialogElement) { this.open = true; });
  vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    queueMicrotask(() => this.dispatchEvent(new Event("close")));
  });
});

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

    await user.click(screen.getByText(/Filters & sort/));
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

    await user.click(screen.getByText(/Filters & sort/));
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

    await user.click(screen.getByText(/Filters & sort/));
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
    await user.click(within(card).getByRole("button", { name: "Save for later" }));

    expect(await within(card).findByRole("button", { name: "Saved for later" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // Ephemeral: no write was attempted.
    expect(fetchMock.mock.calls.length).toBe(callsBefore);
    expect(screen.getByText(/Changes reset on reload/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Like" })).not.toBeInTheDocument();
  });

  it("sets a prospect aside and restores it without sending a taste verdict", async () => {
    const fetchMock = stubFetch();
    const user = userEvent.setup();
    render(<DiscoverPage />);
    const card = await screen.findByRole("article", { name: "Death Note" });
    await user.click(within(card).getByRole("button", { name: "Not interested" }));
    expect(card).toHaveAttribute("data-hidden", "true");
    expect(within(card).getByText(/Set aside/)).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Show again" }));
    expect(card).toHaveAttribute("data-hidden", "false");
    expect(fetchMock.mock.calls.every(([input]) => !String(input).includes("feedback"))).toBe(true);
  });

  it("opens the full inspector from the title, including in StrictMode", async () => {
    stubFetch();
    const user = userEvent.setup();
    render(<StrictMode><DiscoverPage /></StrictMode>);
    await user.click(await screen.findByRole("button", { name: "Death Note" }));
    const dialog = await screen.findByRole("dialog", { name: "Death Note" });
    expect(dialog).toHaveAttribute("open");
    expect(within(dialog).getByText("+76.1")).toBeInTheDocument();
    expect(within(dialog).getByText("Community rating")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("keeps a readable placeholder when the artwork request fails", async () => {
    stubFetch({ ...FEED, recommendations: [{ ...FEED.recommendations[0]!, cover_url: "https://example.test/missing.jpg" }] });
    const { container } = render(<DiscoverPage />);
    await screen.findByText("Death Note");
    fireEvent.error(container.querySelector(".card-art img")!);
    expect(container.querySelector(".card-art img")).toBeNull();
    expect(screen.getByText("No artwork")).toBeInTheDocument();
  });

  it("rolls back a failed save, reports it, and retries the same decision", async () => {
    const profileFeed = { ...FEED, ephemeral: false, state_profile_id: "test-profile" };
    const fetchMock = stubFetch(profileFeed);
    const user = userEvent.setup();
    render(<DiscoverPage />);
    const card = await screen.findByRole("article", { name: "Death Note" });
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ error: {
      code: "network_error", title: "Service unavailable", description: "", solution: "Try again.", retryable: true,
    } }), { status: 503 }));
    await user.click(within(card).getByRole("button", { name: "Save for later" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Decision for Death Note was not saved");
    expect(within(card).getByRole("button", { name: "Save for later" })).toHaveAttribute("aria-pressed", "false");
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ state: { ...FEED.state, watch_later_mal_ids: [1535] } })));
    await user.click(screen.getByRole("button", { name: "Retry decision" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(within(card).getByRole("button", { name: "Saved for later" })).toHaveAttribute("aria-pressed", "true");
  });

  it("serializes profile decisions so a delayed rollback cannot erase another save", async () => {
    const fetchMock = stubFetch({ ...FEED, ephemeral: false, state_profile_id: "test-profile" });
    const user = userEvent.setup();
    render(<DiscoverPage />);
    const first = await screen.findByRole("article", { name: "Death Note" });
    const second = screen.getByRole("article", { name: "Steins;Gate" });
    let complete!: (response: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((resolve) => { complete = resolve; }));
    await user.click(within(first).getByRole("button", { name: "Save for later" }));
    expect(within(second).getByRole("button", { name: "Save for later" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Recommend 5 more" })).toBeDisabled();
    await act(async () => complete(new Response(JSON.stringify({ state: { ...FEED.state, watch_later_mal_ids: [1535] } }))));
    await waitFor(() => expect(within(second).getByRole("button", { name: "Save for later" })).toBeEnabled());
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ state: { ...FEED.state, watch_later_mal_ids: [1535, 9253] } })));
    await user.click(within(second).getByRole("button", { name: "Save for later" }));
    expect(within(first).getByRole("button", { name: "Saved for later" })).toHaveAttribute("aria-pressed", "true");
    expect(within(second).getByRole("button", { name: "Saved for later" })).toHaveAttribute("aria-pressed", "true");
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
