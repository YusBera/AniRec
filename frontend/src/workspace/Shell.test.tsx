import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { Feed, ProfileRead, SystemState, TasteProfile } from "../api/types";
import { ComparePage } from "./ComparePage";
import { boardFacts } from "./profileFacts";
import { ProfilePage } from "./ProfilePage";
import { ActivityConsole, MAX_LINES, readoutRows, renderMeter, useShellState } from "./Shell";
import { Workspace } from "./Workspace";

const SYSTEM: SystemState = { profile: null, needs_setup: true, mal_client_id_present: false, active_operations: [] };
const SAMPLE_FEED = {
  source: "sample", ephemeral: true, profile: null, state_profile_id: null, recommendations: [], hidden_count: 0,
  catalogue: { genres: [], studios: [], years: [], statuses: [] },
  state: { hidden_mal_ids: [], watch_later_mal_ids: [], liked_mal_ids: [], disliked_mal_ids: [], show_hidden: false },
  user_stats: {}, activity_feed_id: "", taste_vector: null,
} as Feed;

beforeEach(() => {
  vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(function (this: HTMLDialogElement) { this.open = true; });
  vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    queueMicrotask(() => this.dispatchEvent(new Event("close")));
  });
  sessionStorage.clear();
});
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe("SYSTEM readout", () => {
  it("takes every value from the API and says unknown when the service did not answer", () => {
    expect(readoutRows(null, false, null).map(([key, value]) => `${key} ${value}`)).toEqual(["ENGINE --", "SOURCE --", "PROFILE --", "MAL --"]);
    expect(readoutRows(null, true, null)[0]!.slice(0, 2)).toEqual(["ENGINE", "OFFLINE"]);
    const busy = { ...SYSTEM, profile: { profile_id: "p", username: "reader" }, mal_client_id_present: true,
      active_operations: [{ id: "1", kind: "recommendation", profile_id: "p", state: "running" as const, event_count: 2 }] };
    expect(readoutRows(busy, false, { ...SAMPLE_FEED, source: "profile" }).map(([key, value]) => `${key} ${value}`))
      .toEqual(["ENGINE BUSY", "SOURCE LIVE", "PROFILE reader", "MAL CLIENT ID"]);
    expect(readoutRows(SYSTEM, false, SAMPLE_FEED).map(([key, value]) => `${key} ${value}`))
      .toEqual(["ENGINE READY", "SOURCE SAMPLE", "PROFILE NONE", "MAL NO CLIENT ID"]);
  });

  it("draws a bounded progress meter", () => {
    expect(renderMeter(3, 5)).toBe("[||||||    ]  60%");
    expect(renderMeter(9, 3)).toBe("[||||||||||] 100%");
    expect(renderMeter(1, 0)).toBe("[          ]   0%");
  });
});

describe("ACTIVITY console", () => {
  function Harness() {
    const shell = useShellState();
    return <ActivityConsole lines={shell.lines} />;
  }

  it("logs the service version and existing operations without inventing times for them", async () => {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
    vi.spyOn(api, "systemState").mockResolvedValue(SYSTEM);
    vi.spyOn(api, "operations").mockResolvedValue({ operations: [{ id: "old", kind: "recommendation", profile_id: "p", state: "succeeded", event_count: 9 }] });
    render(<Harness />);
    const log = screen.getByRole("log", { name: "Activity" });
    await waitFor(() => expect(log).toHaveTextContent("core 1.3.0 online"));
    const history = within(log).getByText("recommendation · succeeded").closest("li")!;
    expect(history).toHaveTextContent("--:--:--");
  });

  it("keeps at most MAX_LINES lines", () => {
    const lines = Array.from({ length: MAX_LINES }, (_, id) => ({ id, time: null, tag: "ENGINE" as const, message: `line ${id}` }));
    render(<ActivityConsole lines={lines} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(MAX_LINES);
  });

  it("says so when nothing has happened yet", () => {
    render(<ActivityConsole lines={[]} />);
    expect(screen.getByText("No activity recorded yet.")).toBeInTheDocument();
  });
});

describe("the shell", () => {
  function stubShell(system: SystemState, feed: Feed = SAMPLE_FEED) {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
    vi.spyOn(api, "systemState").mockResolvedValue(system);
    vi.spyOn(api, "operations").mockResolvedValue({ operations: [] });
    vi.spyOn(api, "feed").mockResolvedValue(feed);
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  }

  it("shows the numbered rail, the sample banner and the BUILD line from the API", async () => {
    stubShell({ ...SYSTEM, needs_setup: false });
    render(<Workspace />);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(["01Discover", "02My Library", "03Profile", "04Compare", "05Settings"]);
    expect(await screen.findByText("Sample data. Connect MyAnimeList to see your own picks.")).toBeInTheDocument();
    expect(await screen.findByText("BUILD 1.3.0")).toBeInTheDocument();
    expect(screen.getByText("Source sample")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("offers first run when setup is needed, and remembers the dismissal for the session", async () => {
    stubShell(SYSTEM);
    const user = userEvent.setup();
    const { unmount } = render(<Workspace />);
    const dialog = await screen.findByRole("dialog", { name: "Welcome" });
    expect(within(dialog).getByText("No account needed. Nothing is saved.")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Next" }));
    expect(within(dialog).getByRole("heading", { name: "MyAnimeList Setup" })).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Connecting a MyAnimeList account is not available in the web client yet.");
    expect(dialog).not.toHaveTextContent(/desktop|install|download/i);
    await user.click(within(dialog).getByRole("button", { name: "Look around with sample data" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    unmount();
    render(<Workspace />);
    await screen.findByText("BUILD 1.3.0");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the honest connect step from the sample banner", async () => {
    stubShell({ ...SYSTEM, needs_setup: false });
    const user = userEvent.setup();
    render(<Workspace />);
    await user.click(await screen.findByRole("button", { name: "Connect my account" }));
    expect(await screen.findByRole("dialog", { name: "MyAnimeList Setup" })).toBeInTheDocument();
  });
});

const PROFILE: TasteProfile = {
  is_sample: true,
  identity: { username: "anirec_sample", member_since: "2017-03-01", completed: 312, episodes: 4829, days_watched: 81.4, mean_score: 7.42 },
  fingerprint: [{ reading_id: "rating-bias", caption: "RATING BIAS", value_text: "-0.43", label: "", detail: "You rate a little under the community average.", tone: "you" }],
  hype_killers: { count: 17, entries: [], biggest: { title: "Tengen Toppa Gurren Lagann", your_score: 3, community_score: 8.71 } },
  hidden_gems: { rate_text: "14%", entries: [], deepest: null },
  studios: { nemesis: { name: "Studio Pierrot", watched: 14, average: 5.1, titles: [{ title: "Naruto", your_score: 7 }], lowest: [{ title: "Bleach", your_score: 4 }, { title: "Bleach", your_score: 4 }] }, readings: [] },
  eras: { buckets: [], seasons: [], season_of_choice: "FALL", golden: null },
} as unknown as TasteProfile;

describe("Profile", () => {
  it("composes the board as the desktop does, from API fields only", () => {
    const facts = boardFacts(PROFILE);
    expect(facts.map((fact) => fact.legend)).toEqual(["RATING BIAS", "BIGGEST HYPE KILL", "NEMESIS", "SEASON OF CHOICE", "DEEP CUTS", "HYPE KILLED"]);
    expect(facts[1]).toMatchObject({ value: "Tengen Toppa Gurren Lagann", caption: "You said 3. Everyone else said 8.71.", tone: "against" });
    expect(facts[2]).toMatchObject({ caption: "Your nemesis studio. 14 watched, averaging 5.10.", evidence: ["Bleach 4"] });
    expect(facts[3]).toMatchObject({ value: "Fall", caption: "You rate fall premieres higher than any other season." });
  });

  it("leads with the reader block and THE READING, and keeps the sample labelled", async () => {
    const read: ProfileRead = { profile: PROFILE, archetype: { archetype_id: "outlier", name: "the outlier", sentence: "When everyone agrees on something, you are the one checking.", evidence: [] } };
    vi.spyOn(api, "profile").mockResolvedValue(read);
    render(<ProfilePage />);
    expect(await screen.findByRole("heading", { name: "anirec_sample" })).toBeInTheDocument();
    expect(screen.getByText("MAL MEMBER SINCE 2017")).toBeInTheDocument();
    expect(screen.getByText("SAMPLE DATA")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "You are the outlier." })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "NOT ON YOUR MAL PROFILE" })).toBeInTheDocument();
    expect(screen.getByText("81.4")).toBeInTheDocument();
  });

  it("says a profile without a reading is still being written rather than inventing one", async () => {
    vi.spyOn(api, "profile").mockResolvedValue({ profile: { ...PROFILE, fingerprint: [] } });
    render(<ProfilePage />);
    expect(await screen.findByRole("heading", { name: "You are still writing the profile." })).toBeInTheDocument();
  });
});

describe("Compare", () => {
  it("never shows the uncalibrated match percentage, even when the report carries one", async () => {
    vi.spyOn(api, "compare").mockImplementation((sample) => Promise.resolve(sample
      ? { sample_names: ["NeoBalls_"], report: { is_sample: true, friend: { username: "NeoBalls_", match_score: 78, match_label: "Strong overlap", total_anime: 412, shared_anime: 96, both_rated: 74 }, sections: [] } }
      : { reason: "username-required", sample_names: [] }));
    const user = userEvent.setup();
    render(<ComparePage />);
    expect(await screen.findByRole("heading", { name: "Compare your taste" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show a sample comparison" }));
    expect(await screen.findByRole("heading", { name: "NeoBalls_" })).toBeInTheDocument();
    expect(screen.getByText("412")).toBeInTheDocument();
    expect(screen.queryByText(/78/)).not.toBeInTheDocument();
    expect(screen.queryByText(/MATCH SCORE/)).not.toBeInTheDocument();
    await act(async () => undefined);
  });
});
