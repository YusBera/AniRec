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
import { DiscoverPage, applyVote, feedCount } from "./DiscoverPage";
import { Workspace } from "../workspace/Workspace";
import { LibraryPage } from "../workspace/LibraryPage";

const CARD = {
  secondary_title: null,
  alternative_titles: [],
  personal_match: 0,
  personal_match_text: "",
  personal_match_available: false,
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
  genre_contributions: [],
  cover_url: null,
  large_cover_url: null,
  mal_url: null,
  media_type: "tv",
  rank: 1,
  fit_pool_size: 13_458,
  ranking_id: "ranking-a",
};

const FEED: Feed = {
  activity_feed_id: "a".repeat(64),
  source: "sample",
  ephemeral: true,
  profile: null,
  state_profile_id: null,
  hidden_count: 0,
  user_stats: { ranking_engine_id: "heuristic" },
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
      fit_rank: 4,
      fit_top_percent: 0.0297,
      mal_score: 8.62,
      genres: ["Psychological", "Supernatural"],
      studios: ["Madhouse"],
      episodes: 37,
      year: 2006,
      reason: "",
      why: {
        schema_version: 1, method: "exact-additive", unit: "ranking-score", baseline: 0,
        total: 2.1, full_score: 2.1, full_rank: 4, ranked_candidate_count: 13_458,
        unavailable_reason: null, influences: [], segments: [{
          kind: "taste", label: "Psychological", facet: "genre", value: 2.4,
          member_count: null, rank_without: null, signal_available: true, feedback_adjustment: null,
          taste: { affinity: 0.8, rarity: 1.2, rated_count: 2, mean_user_score: 9, overall_mean_user_score: 7.4 },
          community: null,
          evidence: [{ mal_id: 19, title: "Monster", user_score: 10, list_status: null, value: null, rank_without: null }],
        }, {
          kind: "community", label: "Community rating", facet: null, value: -0.3,
          member_count: null, rank_without: null, signal_available: true, feedback_adjustment: null,
          taste: null, community: { mean_score: 8.62, scoring_users: 2_000_000 }, evidence: [],
        }],
      },
    },
    {
      ...CARD,
      mal_id: 9253,
      rank: 2,
      display_title: "Steins;Gate",
      fit_rank: 2,
      fit_top_percent: 0.0149,
      mal_score: 9.07,
      genres: ["Comedy"],
      studios: ["White Fox"],
      episodes: 24,
      year: 2011,
      reason: "",
      why: null,
    },
  ],
};

function stubFetch(feed: Feed = FEED) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
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
  it("keeps saved decisions and Library controls when navigating away and back", async () => {
    stubFetch();
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    window.history.replaceState(null, "", "#/discover");
    const user = userEvent.setup();
    render(<Workspace />);
    const card = await screen.findByRole("article", { name: "Death Note" });
    await user.click(within(card).getByRole("button", { name: "Save for later" }));
    const navigate = (hash: string) => act(() => {
      window.history.replaceState(null, "", hash);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    navigate("#/library");
    expect(screen.getByRole("button", { name: "Watch Later · 1" })).toHaveAttribute("aria-pressed", "true");
    await user.type(screen.getByRole("searchbox"), "Death");
    const libraryView = () => within(screen.getByRole("heading", { level: 1, name: "My Library" }).closest("main")!).getByRole("group", { name: "View" });
    await user.click(within(libraryView()).getByRole("button", { name: /List/ }));
    navigate("#/discover");
    expect(within(screen.getByRole("article", { name: "Death Note" })).getByRole("button", { name: "Remove from Watch Later" })).toHaveAttribute("aria-pressed", "true");
    navigate("#/library");
    expect(screen.getByRole("searchbox")).toHaveValue("Death");
    expect(within(libraryView()).getByRole("button", { name: /List/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { level: 1, name: "My Library" })).toHaveFocus();
    await user.click(within(libraryView()).getByRole("button", { name: /Table/ }));
    expect(screen.getByRole("columnheader", { name: "Personal match" })).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Ranked #4 of 13,458 for you")).toBeInTheDocument();
    navigate("#/discover");
    navigate("#/library");
    expect(within(libraryView()).getByRole("button", { name: /Table/ })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(screen.getByRole("table")).getByRole("button", { name: "Remove from Watch Later" }));
    expect(screen.getByRole("heading", { name: "Your Watch Later list is empty" })).toBeInTheDocument();
    window.history.replaceState(null, "", "/");
  });

  it("discloses saved IDs absent from the feed without inventing title evidence", async () => {
    const onVote = vi.fn();
    render(<LibraryPage feed={{ ...FEED, state: { ...FEED.state, watch_later_mal_ids: [99999] } }} pending={false} onVote={onVote} onDetails={vi.fn()} />);
    expect(screen.getByText(/MAL #99999/)).toBeInTheDocument();
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove saved decision" }));
    expect(onVote).toHaveBeenCalledWith(99999, "watch_later", false);
  });

  it("renders a skeleton before the feed arrives, then the cards", async () => {
    stubFetch();
    const { container } = render(<DiscoverPage />);
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThan(0);
    expect(await screen.findByText("Death Note")).toBeInTheDocument();
    expect(screen.getByText("Steins;Gate")).toBeInTheDocument();
    expect(container.querySelectorAll(".skeleton")).toHaveLength(0);
  });

  it("states the feed in plain words, without a second sample note under the shell's banner", async () => {
    stubFetch();
    render(<DiscoverPage />);
    expect(await screen.findByText("2 recommendations")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Discover" })).toBeInTheDocument();
    expect(screen.getByText("Anime picked for you.")).toBeInTheDocument();
    expect(screen.queryByText(/Decisions reset on reload/)).not.toBeInTheDocument();
    expect(screen.queryByText(/IN FEED|SET ASIDE|STATE|READY/)).not.toBeInTheDocument();
  });

  it("filters the feed from a genre pill without another request", async () => {
    const fetchMock = stubFetch();
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await screen.findByText("Death Note");
    const callsBefore = fetchMock.mock.calls.length;

    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(screen.getByText("Genre"));
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

    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(screen.getByText("Genre"));
    await user.click(screen.getByRole("button", { name: "Comedy" }));
    await user.click(screen.getByText("Studio"));
    await user.click(screen.getByRole("button", { name: "Madhouse" }));

    expect(await screen.findByRole("heading", { name: "No matches found" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(await screen.findByText("Death Note")).toBeInTheDocument();
  });

  it("re-sorts without refetching", async () => {
    const user = userEvent.setup();
    stubFetch();
    const { container } = render(<DiscoverPage />);
    await screen.findByText("Death Note");

    await user.click(screen.getByRole("button", { name: "Filters" }));
    await user.click(screen.getByRole("button", { name: "MAL score" }));
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

    expect(await within(card).findByRole("button", { name: "Remove from Watch Later" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // Ephemeral: no write was attempted.
    expect(fetchMock.mock.calls.length).toBe(callsBefore);
    expect(screen.getByText(/Changes reset on reload/)).toBeInTheDocument();
  });

  it("moves a Not interested title out of For You and brings it back from Show not interested", async () => {
    const fetchMock = stubFetch();
    const user = userEvent.setup();
    render(<DiscoverPage />);
    const card = await screen.findByRole("article", { name: "Death Note" });
    await user.click(within(card).getByRole("button", { name: "Not interested" }));
    expect(screen.queryByRole("article", { name: "Death Note" })).not.toBeInTheDocument();
    expect(screen.getByText("1 recommendation")).toBeInTheDocument();
    expect(screen.getByText(/Death Note marked Not interested in this preview/)).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Show not interested" }));
    const restored = await screen.findByRole("article", { name: "Death Note" });
    expect(restored).toHaveAttribute("data-hidden", "true");
    await user.click(within(restored).getByRole("button", { name: "Show this recommendation again" }));
    expect(restored).toHaveAttribute("data-hidden", "false");
    expect(fetchMock.mock.calls.every(([input]) => !String(input).includes("feedback"))).toBe(true);
  });

  it("opens the full inspector from the title, including in StrictMode", async () => {
    stubFetch();
    const user = userEvent.setup();
    render(<StrictMode><DiscoverPage /></StrictMode>);
    await user.click(await screen.findByRole("button", { name: "Death Note" }));
    const dialog = await screen.findByRole("dialog", { name: "Death Note" });
    expect(dialog).toHaveAttribute("open");
    expect(within(dialog).getByText(/SCORE INSPECTOR/)).toBeInTheDocument();
    expect(within(dialog).getByText("Ranked #4 of 13,458 for you")).toBeInTheDocument();
    expect(within(dialog).getByText("+2.4")).toBeInTheDocument();
    expect(within(dialog).getByText("Community rating")).toBeInTheDocument();
    expect(dialog.querySelector(".inspector-position")).toHaveTextContent("02 / 02");
    await user.click(within(dialog).getByRole("button", { name: "Inspect next recommendation" }));
    expect(within(dialog).getByRole("heading", { level: 2, name: "Steins;Gate" })).toBeInTheDocument();
    expect(dialog.querySelector(".inspector-position")).toHaveTextContent("01 / 02");
    expect(within(dialog).getByText("This pick can't be explained")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "READ SYNOPSIS +" }));
    expect(within(dialog).getByRole("button", { name: "HIDE SYNOPSIS −" })).toHaveAttribute("aria-expanded", "true");
    await user.click(within(dialog).getByRole("button", { name: "Close score inspector" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(within(screen.getByRole("article", { name: "Steins;Gate" })).getByRole("button", { name: "Steins;Gate" })).toHaveFocus());
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
    expect(within(card).getByRole("button", { name: "Remove from Watch Later" })).toHaveAttribute("aria-pressed", "true");
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
    expect(screen.getByRole("button", { name: "Refresh" })).toBeDisabled();
    await act(async () => complete(new Response(JSON.stringify({ state: { ...FEED.state, watch_later_mal_ids: [1535] } }))));
    await waitFor(() => expect(within(second).getByRole("button", { name: "Save for later" })).toBeEnabled());
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ state: { ...FEED.state, watch_later_mal_ids: [1535, 9253] } })));
    await user.click(within(second).getByRole("button", { name: "Save for later" }));
    await waitFor(() => expect(within(second).getByRole("button", { name: "Remove from Watch Later" })).toHaveAttribute("aria-pressed", "true"));
    expect(within(first).getByRole("button", { name: "Remove from Watch Later" })).toHaveAttribute("aria-pressed", "true");
  });

  it("paginates a growing feed without mounting every recommendation", async () => {
    const recommendations = Array.from({ length: 60 }, (_, index) => ({
      ...FEED.recommendations[0]!, mal_id: 10_000 + index,
      display_title: `Title ${index + 1}`, rank: index + 1,
      fit_rank: null, fit_pool_size: null, fit_top_percent: null, ranking_id: null, why: null,
    }));
    stubFetch({ ...FEED, recommendations });
    const user = userEvent.setup();
    render(<DiscoverPage />);
    expect(await screen.findByRole("heading", { name: "Title 1" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Title 51" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next recommendations page" }));
    expect(screen.getByRole("heading", { name: "Title 51" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Title 1" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Recommendations" })).toHaveFocus();
  });

  it("rebuilds the feed by itself when continuing refuses a stale ranking", async () => {
    class FakeEventSource {
      static instances: FakeEventSource[] = [];
      listeners = new Map<string, Array<(event: Event) => void>>();
      constructor(readonly url: string) { FakeEventSource.instances.push(this); }
      addEventListener(type: string, listener: (event: Event) => void) {
        this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
      }
      close() {}
      emit(type: string, data: unknown) {
        for (const listener of this.listeners.get(type) ?? []) listener(new MessageEvent(type, { data: JSON.stringify(data) }));
      }
    }
    vi.stubGlobal("EventSource", FakeEventSource);
    const profileFeed = { ...FEED, ephemeral: false, state_profile_id: "test-profile" };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/discover/feed")) return new Response(JSON.stringify(profileFeed), { headers: { "Content-Type": "application/json" } });
      if (url.endsWith("/api/discover/activity")) return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
      if (url.includes("/api/operations/")) return new Response(JSON.stringify({ id: url.endsWith("/refresh") ? "refresh-1" : "more-1" }), { headers: { "Content-Type": "application/json" } });
      return new Response("{}", { headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await user.click(await screen.findByRole("button", { name: "Next page, load the next 50 recommendations" }));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const operations = () => fetchMock.mock.calls.map(([input]) => String(input)).filter((url) => url.includes("/api/operations/") && !url.includes("/events"));
    expect(operations().at(-1)).toMatch(/\/api\/operations\/more-recommendations$/);
    act(() => FakeEventSource.instances[0]!.emit("error", {
      code: "stale_ranking",
      title: "Feed is out of date",
      description: "Ranking inputs changed. Generate a new feed to continue.",
      solution: "Generate a new feed.",
      retryable: false,
    }));
    await waitFor(() => expect(operations().at(-1)).toMatch(/\/api\/operations\/refresh$/));
    expect(screen.queryByRole("button", { name: "Generate a new feed" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(2);
  });

  it("disables generation when there is no profile to generate for", async () => {
    stubFetch();
    render(<DiscoverPage />);
    expect(await screen.findByRole("button", { name: "Refresh" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Recommend 5 more" })).not.toBeInTheDocument();
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

describe("optimistic recommendation state", () => {
  const base = {
    hidden_mal_ids: [],
    watch_later_mal_ids: [],
    liked_mal_ids: [],
    disliked_mal_ids: [7],
    show_hidden: false,
  };

  it("adds and removes without duplicating", () => {
    const once = applyVote(base, 3, "watch_later", true);
    const twice = applyVote(once, 3, "watch_later", true);
    expect(twice.watch_later_mal_ids).toEqual([3]);
    expect(applyVote(twice, 3, "watch_later", false).watch_later_mal_ids).toEqual([]);
  });
});

it("loads saved metadata outside the feed and retains honest missing-score state", async () => {
  const { api } = await import("../api/client");
  const model = { ...FEED.recommendations[0]!, mal_id: 19, display_title: "Monster", fit_rank: null, fit_pool_size: null, fit_top_percent: null, ranking_id: null };
  vi.spyOn(api, "library").mockResolvedValue({ profile_id: "reader", recommendations: [model] });
  const feed: Feed = { ...FEED, source: "profile", ephemeral: false, state_profile_id: "reader", recommendations: [], state: { ...FEED.state, watch_later_mal_ids: [19] } };
  const details = vi.fn();
  render(<LibraryPage feed={feed} pending={false} onVote={vi.fn()} onDetails={details} />);
  expect(await screen.findByRole("heading", { name: "Monster" })).toBeInTheDocument();
  expect(screen.getByText("Personal match unavailable")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Inspect Monster" }));
  expect(details).toHaveBeenCalledWith(model, [model]);
});

it("paginates saved titles in Library and resets to the first page when searching", async () => {
  const recommendations = Array.from({ length: 60 }, (_, index) => ({
    ...FEED.recommendations[0]!, mal_id: 20_000 + index,
    display_title: `Saved ${index + 1}`, rank: index + 1,
    fit_rank: null, fit_pool_size: null, fit_top_percent: null, ranking_id: null, why: null,
  }));
  const feed: Feed = { ...FEED, recommendations, state: { ...FEED.state, watch_later_mal_ids: recommendations.map(model => model.mal_id) } };
  const user = userEvent.setup();
  render(<LibraryPage feed={feed} pending={false} onVote={vi.fn()} onDetails={vi.fn()} />);
  expect(screen.getByRole("heading", { name: "Saved 1" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Saved 51" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next saved titles page" }));
  expect(screen.getByRole("heading", { name: "Saved 51" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /Watch Later/ })).toHaveFocus();
  await user.type(screen.getByRole("searchbox", { name: "Find a saved title" }), "Saved 1");
  expect(screen.getByRole("heading", { name: "Saved 1" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Next saved titles page" })).not.toBeInTheDocument();
});

it("paginates unresolved saved IDs instead of mounting the whole missing list", async () => {
  const ids = Array.from({ length: 60 }, (_, index) => 30_000 + index);
  const feed: Feed = { ...FEED, recommendations: [], state: { ...FEED.state, watch_later_mal_ids: ids } };
  render(<LibraryPage feed={feed} pending={false} onVote={vi.fn()} onDetails={vi.fn()} />);
  expect(screen.getByText(/MAL #30000/)).toBeInTheDocument();
  expect(screen.queryByText(/MAL #30059/)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Next unresolved saved ids page/i }));
  expect(screen.getByText(/MAL #30059/)).toBeInTheDocument();
});

describe("the PySide card and header", () => {
  it("builds the card in recommendation_card.py order, with nothing over the poster and two verdicts", async () => {
    stubFetch({ ...FEED, recommendations: [{ ...FEED.recommendations[0]!, reason: "Matches your interests in Psychological.", mal_url: "https://myanimelist.net/anime/1535" }] });
    render(<DiscoverPage />);
    const card = await screen.findByRole("article", { name: "Death Note" });
    const art = card.querySelector(".card-art")!;
    expect(art.children).toHaveLength(1);
    expect(art.textContent).not.toMatch(/#\d|Ranked|%/);
    const order = [...card.children].map((node) => node.className.split(" ")[0]);
    expect(order).toEqual(["card-art", "card-fit", "card-title", "card-secondary", "card-verdicts", "card-tags", "card-meta", "card-mal", "card-reason", "card-utilities"]);
    expect(within(card).getByText("Ranked #4 of 13,458 for you")).toBeInTheDocument();
    expect(within(card).getByText("Matches your interests in Psychological.")).toBeInTheDocument();
    const verdicts = within(within(card).getByRole("group", { name: "Decisions for Death Note" })).getAllByRole("button");
    expect(verdicts.map((button) => button.getAttribute("aria-label"))).toEqual(["Save for later", "Not interested"]);
    expect(verdicts[1]).toHaveAttribute("title", "Stop recommending this anime. It stays in Not interested.");
    expect(within(card).queryByRole("button", { name: /like/i })).not.toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Open the full breakdown for Death Note" })).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Open Death Note on MyAnimeList (external)" })).toBeInTheDocument();
  });

  it("shows no reason line when the API sent none, and states an unavailable rank in words", async () => {
    stubFetch({ ...FEED, recommendations: [{ ...FEED.recommendations[1]!, fit_rank: null, fit_pool_size: null, reason: "" }] });
    render(<DiscoverPage />);
    const card = await screen.findByRole("article", { name: "Steins;Gate" });
    expect(card.querySelector(".card-reason")).toBeEmptyDOMElement();
    expect(within(card).getByText("Personal match unavailable")).toBeInTheDocument();
  });

  it("counts the feed in plain words (D-019)", () => {
    expect(feedCount(1)).toBe("1 recommendation");
    expect(feedCount(0)).toBe("0 recommendations");
    expect(feedCount(1250)).toBe("1,250 recommendations");
  });

  it("offers no RUN ANALYSIS, More or connect action, and disables Refresh on the sample feed with the reason", async () => {
    stubFetch();
    render(<DiscoverPage />);
    const refresh = await screen.findByRole("button", { name: "Refresh" });
    expect(refresh).toBeDisabled();
    expect(refresh).toHaveAttribute("title", "Not available for the sample library.");
    expect(screen.queryByRole("button", { name: /Recommend/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /RUN ANALYSIS/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/connect/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Updating your recommendations/)).not.toBeInTheDocument();
  });

  it("refreshes, says it is updating with the stream's progress, and reloads the feed when it succeeds", async () => {
    class FakeEventSource {
      static instances: FakeEventSource[] = [];
      listeners = new Map<string, Array<(event: Event) => void>>();
      constructor(readonly url: string) { FakeEventSource.instances.push(this); }
      addEventListener(type: string, listener: (event: Event) => void) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]); }
      close() {}
      emit(type: string, data: unknown) { for (const listener of this.listeners.get(type) ?? []) listener(new MessageEvent(type, { data: JSON.stringify(data) })); }
    }
    vi.stubGlobal("EventSource", FakeEventSource);
    const profileFeed = { ...FEED, source: "profile" as const, ephemeral: false, state_profile_id: "test-profile" };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/discover/feed")) return new Response(JSON.stringify(profileFeed), { headers: { "Content-Type": "application/json" } });
      if (url.endsWith("/api/operations/refresh")) return new Response(JSON.stringify({ id: "run-1", kind: "refresh", profile_id: "test-profile", state: "running", event_count: 0 }), { status: 202, headers: { "Content-Type": "application/json" } });
      return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await user.click(await screen.findByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    act(() => FakeEventSource.instances[0]!.emit("progress", { stage_id: "fetch", message: "Fetch completed anime", current: 1, total: 4, cancellable: true }));
    expect(screen.getByText(/Updating your recommendations…/)).toBeInTheDocument();
    expect(screen.getAllByText(/Fetch completed anime/).length).toBeGreaterThan(0);
    const feedCalls = () => fetchMock.mock.calls.filter(([input]) => String(input).includes("/api/discover/feed")).length;
    const before = feedCalls();
    act(() => FakeEventSource.instances[0]!.emit("finished", { state: "succeeded" }));
    await waitFor(() => expect(feedCalls()).toBe(before + 1));
    expect(screen.queryByText(/Updating your recommendations/)).not.toBeInTheDocument();
  });

  it("words a 409 as another operation already running, not as a failed request", async () => {
    const profileFeed = { ...FEED, source: "profile" as const, ephemeral: false, state_profile_id: "test-profile" };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/discover/feed")) return new Response(JSON.stringify(profileFeed), { headers: { "Content-Type": "application/json" } });
      if (url.includes("/api/operations/")) return new Response(JSON.stringify({ error: {
        code: "invalid_request", title: "Operation is already running: recommendation:test-profile",
        description: "Operation is already running: recommendation:test-profile", solution: "", retryable: false,
      } }), { status: 409, headers: { "Content-Type": "application/json" } });
      return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
    }));
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await user.click(await screen.findByRole("button", { name: "Refresh" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Another operation is already running");
    expect(alert).toHaveTextContent("Operation is already running: recommendation:test-profile");
    expect(alert).not.toHaveTextContent("reloads");
  });

  it("keeps the service's own words for a 409 that is not a running operation", async () => {
    const profileFeed = { ...FEED, source: "profile" as const, ephemeral: false, state_profile_id: "test-profile" };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/discover/feed")) return new Response(JSON.stringify(profileFeed), { headers: { "Content-Type": "application/json" } });
      if (url.includes("/api/operations/")) return new Response(JSON.stringify({ error: {
        code: "invalid_request", title: "No active profile. Complete setup first.",
        description: "No active profile. Complete setup first.", solution: "", retryable: false,
      } }), { status: 409, headers: { "Content-Type": "application/json" } });
      return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
    }));
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await user.click(await screen.findByRole("button", { name: "Refresh" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No active profile. Complete setup first.");
    expect(alert).not.toHaveTextContent("Another operation");
  });

  it("returns focus to the visible Library card, not the hidden Discover copy, when the inspector closes", async () => {
    stubFetch({ ...FEED, state: { ...FEED.state, watch_later_mal_ids: [1535] } });
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    window.history.replaceState(null, "", "#/library");
    const user = userEvent.setup();
    render(<Workspace />);
    const libraryMain = (await screen.findByRole("heading", { level: 1, name: "My Library" })).closest("main")!;
    const card = await within(libraryMain).findByRole("article", { name: "Death Note" });
    await user.click(within(card).getByRole("button", { name: "Death Note" }));
    const dialog = await screen.findByRole("dialog", { name: "Death Note" });
    await user.click(within(dialog).getByRole("button", { name: "Close score inspector" }));
    await waitFor(() => expect(within(card).getByRole("button", { name: "Death Note" })).toHaveFocus());
    window.history.replaceState(null, "", "/");
  });

  it("ignores a superseded feed read so a stale state cannot land over a newer one", async () => {
    const profileFeed = { ...FEED, source: "profile" as const, ephemeral: false, state_profile_id: "test-profile", hidden_count: 1 };
    let releaseFirst!: () => void;
    let reads = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/discover/feed")) {
        reads += 1;
        // Read 2 is the superseded one and carries a different saved list.
        const saved = reads === 1 ? [] : reads === 2 ? [1, 2] : [3];
        const body = new Response(JSON.stringify({ ...profileFeed, state: { ...FEED.state, watch_later_mal_ids: saved } }), { headers: { "Content-Type": "application/json" } });
        if (reads === 2) await new Promise<void>((resolve) => { releaseFirst = resolve; });
        return body;
      }
      return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
    }));
    const user = userEvent.setup();
    render(<DiscoverPage />);
    const toggle = await screen.findByRole("checkbox", { name: "Show not interested" });
    await user.click(toggle);
    await user.click(toggle);
    // The Watch Later count on the (hidden) Library tab shows which read landed.
    const savedTab = (count: number) => screen.queryByRole("button", { name: `Watch Later · ${count}`, hidden: true });
    await waitFor(() => expect(savedTab(1)).toBeInTheDocument());
    await act(async () => releaseFirst());
    expect(savedTab(1)).toBeInTheDocument();
    expect(savedTab(2)).not.toBeInTheDocument();
    expect(reads).toBe(3);
  });

  it("renders List and Table with 2:3 thumbnails and the same decisions", async () => {
    stubFetch();
    const user = userEvent.setup();
    const { container } = render(<DiscoverPage />);
    await screen.findByRole("article", { name: "Death Note" });
    await user.click(screen.getByRole("button", { name: /List/ }));
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
    expect(container.querySelectorAll(".feed-row .row-art")).toHaveLength(2);
    expect(screen.getByText("Madhouse · 2006 · 12 episodes · MAL 8.62")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Table/ }));
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(["Rank", "Title", "Personal match", "MAL score", "Genres", "Year", "Status", "Episodes", "Actions"]);
    expect(container.querySelectorAll(".feed-table .table-thumb")).toHaveLength(2);
    await user.click(within(table).getAllByRole("button", { name: "Watch Later" })[0]!);
    expect(within(table).getByRole("button", { name: "Remove from Watch Later" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("My Library collections", () => {
  it("opens on Watch Later, then Not interested, with the desktop's empty-state copy", async () => {
    const user = userEvent.setup();
    render(<LibraryPage feed={FEED} pending={false} onVote={vi.fn()} onDetails={vi.fn()} />);
    const tabs = within(screen.getByRole("group", { name: "Library collection" })).getAllByRole("button");
    expect(tabs.map((tab) => tab.getAttribute("aria-label"))).toEqual(["Watch Later · 0", "Not interested · 0"]);
    expect(tabs[0]).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: "Your Watch Later list is empty" })).toBeInTheDocument();
    expect(screen.getByText("Save an anime from any card and it will appear in this collection.")).toBeInTheDocument();
    await user.click(tabs[1]!);
    expect(screen.getByRole("heading", { name: "Nothing set aside yet" })).toBeInTheDocument();
  });

  it("restores a Not interested title from its collection", async () => {
    const onVote = vi.fn();
    const user = userEvent.setup();
    render(<LibraryPage feed={{ ...FEED, state: { ...FEED.state, hidden_mal_ids: [1535] } }} pending={false} onVote={onVote} onDetails={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Not interested · 1" }));
    const card = screen.getByRole("article", { name: "Death Note" });
    await user.click(within(card).getByRole("button", { name: "Show this recommendation again" }));
    expect(onVote.mock.calls[0]!.slice(0, 3)).toEqual([1535, "hidden", false]);
  });
});

describe("design-port review fixes", () => {
  it("numbers the Table's Rank column by the reader's order, not the backend rank (CHANGE [RANK])", async () => {
    // Personal fit puts Steins;Gate (fit 2) above Death Note (fit 4); the
    // backend ranks are 2 and 1, which the old column printed as-is.
    stubFetch();
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await user.click(await screen.findByRole("button", { name: /Table/ }));
    const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
    expect(within(rows[0]!).getByRole("rowheader")).toHaveTextContent("Steins;Gate");
    expect(within(rows[0]!).getAllByRole("cell")[0]).toHaveTextContent(/^1$/);
    expect(within(rows[1]!).getAllByRole("cell")[0]).toHaveTextContent(/^2$/);
  });

  it("collapses tags past the card's reservation into a +n that names the rest", async () => {
    const genres = ["Action", "Drama", "Fantasy", "Mystery", "Romance", "Sci-Fi", "Suspense"];
    stubFetch({ ...FEED, recommendations: [{ ...FEED.recommendations[1]!, genres, studios: ["White Fox", "Studio B"] }] });
    render(<DiscoverPage />);
    const card = await screen.findByRole("article", { name: "Steins;Gate" });
    const tags = card.querySelector(".card-tags")!;
    // Studio + 3 genres + "+n" fill the five slots; the rest are named.
    const more = within(tags as HTMLElement).getByText(/^\+5/);
    expect(more.closest(".card-tag")).toHaveAttribute("title", "Studio B · Mystery · Romance · Sci-Fi · Suspense");
    expect(tags).toHaveTextContent("more: Studio B, Mystery, Romance, Sci-Fi, Suspense");
  });

  it("says the reader is all caught up when every title was marked Not interested before a reload", async () => {
    const profileFeed = { ...FEED, source: "profile" as const, ephemeral: false, state_profile_id: "p", recommendations: [], hidden_count: 2 };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input).includes("/api/discover/feed")
      ? new Response(JSON.stringify(profileFeed), { headers: { "Content-Type": "application/json" } })
      : new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } })));
    render(<DiscoverPage />);
    expect(await screen.findByRole("heading", { name: "You’re all caught up" })).toBeInTheDocument();
    expect(screen.queryByText("No recommendations yet")).not.toBeInTheDocument();
  });

  describe("a progress stream that closes before the operation reports", () => {
    class ClosingEventSource {
      static instances: ClosingEventSource[] = [];
      static CLOSED = 2;
      readyState = 0;
      listeners = new Map<string, Array<(event: Event) => void>>();
      constructor(readonly url: string) { ClosingEventSource.instances.push(this); }
      addEventListener(type: string, listener: (event: Event) => void) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]); }
      close() { this.readyState = ClosingEventSource.CLOSED; }
      drop() { this.readyState = ClosingEventSource.CLOSED; for (const listener of this.listeners.get("error") ?? []) listener(new Event("error")); }
    }
    const profileFeed = { ...FEED, source: "profile" as const, ephemeral: false, state_profile_id: "test-profile" };

    function stub(operation: () => Response) {
      ClosingEventSource.instances = [];
      vi.stubGlobal("EventSource", ClosingEventSource);
      const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/discover/feed")) return new Response(JSON.stringify(profileFeed), { headers: { "Content-Type": "application/json" } });
        if (url.endsWith("/api/operations/refresh")) return new Response(JSON.stringify({ id: "run-1", kind: "refresh", profile_id: "test-profile", state: "running", event_count: 0 }), { status: 202, headers: { "Content-Type": "application/json" } });
        if (url.endsWith("/api/operations/run-1")) return operation();
        return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
      });
      vi.stubGlobal("fetch", fetchMock);
      return fetchMock;
    }

    it("reads the operation's own outcome and reloads when it had finished", async () => {
      const fetchMock = stub(() => new Response(JSON.stringify({ id: "run-1", kind: "refresh", profile_id: "test-profile", state: "succeeded", event_count: 3 }), { headers: { "Content-Type": "application/json" } }));
      const user = userEvent.setup();
      render(<DiscoverPage />);
      await user.click(await screen.findByRole("button", { name: "Refresh" }));
      await waitFor(() => expect(ClosingEventSource.instances).toHaveLength(1));
      const feedCalls = () => fetchMock.mock.calls.filter(([input]) => String(input).includes("/api/discover/feed")).length;
      const before = feedCalls();
      act(() => ClosingEventSource.instances[0]!.drop());
      await waitFor(() => expect(feedCalls()).toBe(before + 1));
      expect(await screen.findByRole("button", { name: "Refresh" })).toBeEnabled();
      expect(screen.queryByText(/Updating your recommendations/)).not.toBeInTheDocument();
    });

    it("stops claiming to run, and says the outcome is unknown, when the service cannot answer", async () => {
      stub(() => new Response("{}", { status: 404 }));
      const user = userEvent.setup();
      render(<DiscoverPage />);
      await user.click(await screen.findByRole("button", { name: "Refresh" }));
      await waitFor(() => expect(ClosingEventSource.instances).toHaveLength(1));
      act(() => ClosingEventSource.instances[0]!.drop());
      expect(await screen.findByRole("alert")).toHaveTextContent("Lost contact with the running operation");
      expect(screen.queryByText(/Updating your recommendations/)).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
    });
  });
});

describe("automatic refresh and continuous pages (D-018)", () => {
  class ScriptedEventSource {
    static instances: ScriptedEventSource[] = [];
    listeners = new Map<string, Array<(event: Event) => void>>();
    constructor(readonly url: string) { ScriptedEventSource.instances.push(this); }
    addEventListener(type: string, listener: (event: Event) => void) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]); }
    close() {}
    emit(type: string, data: unknown) { for (const listener of this.listeners.get(type) ?? []) listener(new MessageEvent(type, { data: JSON.stringify(data) })); }
  }
  const titles = (count: number) => Array.from({ length: count }, (_, index) => ({
    ...FEED.recommendations[0]!, mal_id: 40_000 + index, display_title: `Pick ${index + 1}`, rank: index + 1,
    fit_rank: index + 1, fit_pool_size: 22_000, fit_top_percent: null, ranking_id: "r".repeat(64), why: null,
  }));

  function stubProfile(feeds: Feed[]) {
    ScriptedEventSource.instances = [];
    vi.stubGlobal("EventSource", ScriptedEventSource);
    let read = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/discover/feed")) {
        const feed = feeds[Math.min(read, feeds.length - 1)]!;
        read += 1;
        return new Response(JSON.stringify(feed), { headers: { "Content-Type": "application/json" } });
      }
      if (url.includes("/api/operations/") && init?.method === "POST") {
        const kind = url.split("/").at(-1);
        return new Response(JSON.stringify({ id: `${kind}-1`, kind, profile_id: "p", state: "running", event_count: 0 }), { status: 202, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }
  const profileFeed = (count: number): Feed => ({ ...FEED, source: "profile", ephemeral: false, state_profile_id: "p", recommendations: titles(count) });
  const posted = (fetchMock: ReturnType<typeof vi.fn>) => fetchMock.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "POST")
    .map(([input, init]) => [String(input).split("/").at(-1), JSON.parse(String((init as RequestInit).body ?? "{}"))]);

  it("continues the ranking with the next 50 from the last page and lands on the new page", async () => {
    const fetchMock = stubProfile([profileFeed(50), profileFeed(100)]);
    const user = userEvent.setup();
    render(<DiscoverPage />);
    expect(await screen.findByRole("heading", { name: "Pick 50" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next page, load the next 50 recommendations" }));
    await waitFor(() => expect(ScriptedEventSource.instances).toHaveLength(1));
    expect(posted(fetchMock).at(-1)).toEqual(["more-recommendations", expect.objectContaining({ count: 50 })]);
    act(() => ScriptedEventSource.instances[0]!.emit("finished", { state: "succeeded" }));
    expect(await screen.findByRole("heading", { name: "Pick 51" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Pick 1" })).not.toBeInTheDocument();
  });

  it("refreshes a profile's feed once per session when the workspace opens it, never the sample", async () => {
    sessionStorage.clear();
    const fetchMock = stubProfile([profileFeed(3)]);
    const { unmount } = render(<DiscoverPage autoRefresh />);
    await waitFor(() => expect(posted(fetchMock)).toEqual([["refresh", expect.objectContaining({ count: 50 })]]));
    act(() => ScriptedEventSource.instances[0]!.emit("finished", { state: "succeeded" }));
    unmount();
    render(<DiscoverPage autoRefresh />);
    await screen.findByRole("heading", { name: "Pick 1" });
    expect(posted(fetchMock)).toHaveLength(1);

    sessionStorage.clear();
    const sampleFetch = stubProfile([FEED]);
    render(<DiscoverPage autoRefresh />);
    await screen.findAllByRole("article");
    expect(posted(sampleFetch)).toEqual([]);
  });
});

describe("automatic refresh review fixes", () => {
  class Source {
    static instances: Source[] = [];
    listeners = new Map<string, Array<(event: Event) => void>>();
    constructor(readonly url: string) { Source.instances.push(this); }
    addEventListener(type: string, listener: (event: Event) => void) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]); }
    close() {}
    emit(type: string, data: unknown) { for (const listener of this.listeners.get(type) ?? []) listener(new MessageEvent(type, { data: JSON.stringify(data) })); }
  }
  const picks = (count: number) => Array.from({ length: count }, (_, index) => ({
    ...FEED.recommendations[0]!, mal_id: 50_000 + index, display_title: `Pick ${index + 1}`, rank: index + 1,
    fit_rank: index + 1, fit_pool_size: 22_000, fit_top_percent: null, ranking_id: "r".repeat(64), why: null,
  }));
  const profileFeed = (count: number): Feed => ({ ...FEED, source: "profile", ephemeral: false, state_profile_id: "p", recommendations: picks(count) });
  function stub(feeds: Feed[]) {
    Source.instances = [];
    vi.stubGlobal("EventSource", Source);
    let read = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/discover/feed")) {
        const feed = feeds[Math.min(read, feeds.length - 1)]!;
        read += 1;
        return new Response(JSON.stringify(feed), { headers: { "Content-Type": "application/json" } });
      }
      if (url.includes("/api/operations/") && init?.method === "POST") {
        const kind = url.split("/").at(-1);
        return new Response(JSON.stringify({ id: `${kind}-${Source.instances.length}`, kind, profile_id: "p", state: "running", event_count: 0 }), { status: 202, headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }
  const kinds = (fetchMock: ReturnType<typeof vi.fn>) => fetchMock.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "POST")
    .map(([input]) => String(input).split("/").at(-1));
  const stale = { code: "invalid_request", title: "Feed is out of date", description: "Generate a new feed to see more recommendations.", solution: "", retryable: false };

  it("lands on the page holding the first new pick when fewer than a full last page were shown", async () => {
    stub([profileFeed(73), profileFeed(123)]);
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await screen.findByRole("heading", { name: "Pick 1" });
    await user.click(screen.getByRole("button", { name: "Next recommendations page" }));
    await user.click(screen.getByRole("button", { name: "Next page, load the next 50 recommendations" }));
    await waitFor(() => expect(Source.instances).toHaveLength(1));
    act(() => Source.instances[0]!.emit("finished", { state: "succeeded" }));
    expect(await screen.findByRole("heading", { name: "Pick 74" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pick 51" })).toBeInTheDocument();
  });

  it("rebuilds once on a stale refusal, then reports a second refusal in the service's own words", async () => {
    const fetchMock = stub([profileFeed(3)]);
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await user.click(await screen.findByRole("button", { name: "Next page, load the next 50 recommendations" }));
    await waitFor(() => expect(Source.instances).toHaveLength(1));
    act(() => Source.instances[0]!.emit("error", stale));
    await waitFor(() => expect(kinds(fetchMock)).toEqual(["more-recommendations", "refresh"]));
    await waitFor(() => expect(Source.instances).toHaveLength(2));
    act(() => Source.instances[1]!.emit("finished", { state: "failed" }));
    await user.click(screen.getByRole("button", { name: "Next page, load the next 50 recommendations" }));
    await waitFor(() => expect(Source.instances).toHaveLength(3));
    act(() => Source.instances[2]!.emit("error", stale));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Feed is out of date");
    expect(alert).not.toHaveTextContent("rebuilding");
    expect(kinds(fetchMock)).toEqual(["more-recommendations", "refresh", "more-recommendations"]);
  });

  it("refreshes an active profile that has no feed yet, although the sample library is shown", async () => {
    sessionStorage.clear();
    const fetchMock = stub([FEED]);
    render(<DiscoverPage autoRefresh activeProfileId="p" />);
    await waitFor(() => expect(kinds(fetchMock)).toEqual(["refresh"]));
  });

  it("does not repeat a reconnect advice the web client cannot follow", async () => {
    stub([profileFeed(3)]);
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await user.click(await screen.findByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(Source.instances).toHaveLength(1));
    act(() => Source.instances[0]!.emit("error", {
      code: "auth_error", title: "Account connection problem",
      description: "The MyAnimeList connection is unavailable or no longer valid.",
      solution: "Reconnect your MyAnimeList account and retry the operation.", retryable: true,
    }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The MyAnimeList connection is unavailable or no longer valid.");
    expect(alert).not.toHaveTextContent(/reconnect/i);
  });
});


describe("automatic refresh, final review", () => {
  class Stream {
    static instances: Stream[] = [];
    listeners = new Map<string, Array<(event: Event) => void>>();
    constructor(readonly url: string) { Stream.instances.push(this); }
    addEventListener(type: string, listener: (event: Event) => void) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]); }
    close() {}
    emit(type: string, data: unknown) { for (const listener of this.listeners.get(type) ?? []) listener(new MessageEvent(type, { data: JSON.stringify(data) })); }
  }
  const feed: Feed = { ...FEED, source: "profile", ephemeral: false, state_profile_id: "p" };
  function stub(start: () => Response) {
    Stream.instances = [];
    vi.stubGlobal("EventSource", Stream);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/discover/feed")) return new Response(JSON.stringify(feed), { headers: { "Content-Type": "application/json" } });
      if (url.includes("/api/operations/") && init?.method === "POST") return start();
      return new Response(JSON.stringify({ enabled: false }), { headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }
  const refreshes = (fetchMock: ReturnType<typeof vi.fn>) => fetchMock.mock.calls
    .filter(([input, init]) => (init as RequestInit | undefined)?.method === "POST" && String(input).endsWith("/refresh")).length;
  const running = () => new Response(JSON.stringify({ id: `refresh-${Stream.instances.length}`, kind: "refresh", profile_id: "p", state: "running", event_count: 0 }), { status: 202, headers: { "Content-Type": "application/json" } });

  it("refreshes once even when session storage cannot be written, including after a failure", async () => {
    sessionStorage.clear();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    const fetchMock = stub(running);
    render(<DiscoverPage autoRefresh />);
    await waitFor(() => expect(Stream.instances).toHaveLength(1));
    act(() => Stream.instances[0]!.emit("finished", { state: "failed" }));
    await screen.findByRole("heading", { name: "Death Note" });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)); });
    expect(refreshes(fetchMock)).toBe(1);
  });

  it("stays quiet when the automatic refresh meets another tab's running operation", async () => {
    sessionStorage.clear();
    stub(() => new Response(JSON.stringify({ error: {
      code: "invalid_request", title: "Operation is already running: refresh:p",
      description: "Operation is already running: refresh:p", solution: "", retryable: false,
    } }), { status: 409, headers: { "Content-Type": "application/json" } }));
    render(<DiscoverPage autoRefresh />);
    await screen.findByRole("heading", { name: "Death Note" });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)); });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("still reports a 409 when the reader pressed Refresh", async () => {
    sessionStorage.setItem("anirec.feedRefreshed", JSON.stringify(["p"]));
    stub(() => new Response(JSON.stringify({ error: {
      code: "invalid_request", title: "Operation is already running: refresh:p",
      description: "Operation is already running: refresh:p", solution: "", retryable: false,
    } }), { status: 409, headers: { "Content-Type": "application/json" } }));
    const user = userEvent.setup();
    render(<DiscoverPage autoRefresh />);
    await user.click(await screen.findByRole("button", { name: "Refresh" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Another operation is already running");
  });

  it("drops reconnect advice for an authorization timeout too", async () => {
    stub(running);
    const user = userEvent.setup();
    render(<DiscoverPage />);
    await user.click(await screen.findByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(Stream.instances).toHaveLength(1));
    act(() => Stream.instances[0]!.emit("error", {
      code: "auth_timeout", title: "Account connection timed out",
      description: "MyAnimeList authorization was not completed in time.",
      solution: "Start the connection again and finish authorization in the browser.", retryable: true,
    }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("MyAnimeList authorization was not completed in time.");
    expect(alert).not.toHaveTextContent(/connection again/i);
  });
});
