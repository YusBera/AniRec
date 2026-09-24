import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { Feed, ProfileRead, SystemState, TasteProfile } from "../api/types";
import { ComparePage } from "./ComparePage";
import { boardFacts } from "./profileFacts";
import { ProfilePage } from "./ProfilePage";
import { MAX_NOTICES, operationNotice, useShellState } from "./Shell";
import { Notifications } from "./TopBar";
import { Workspace } from "./Workspace";

const SYSTEM: SystemState = { profile: null, needs_setup: true, mal_client_id_present: false, active_operations: [] };
const SAMPLE_FEED = {
  source: "sample", ephemeral: true, profile: null, state_profile_id: null, recommendations: [], hidden_count: 0,
  catalogue: { genres: [], studios: [], years: [], statuses: [] },
  state: { hidden_mal_ids: [], watch_later_mal_ids: [], liked_mal_ids: [], disliked_mal_ids: [], show_hidden: false },
  user_stats: {}, activity_feed_id: "",
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

describe("notifications (D-019)", () => {
  it("words operation outcomes as a reader would, and says nothing for kinds they would not recognise", () => {
    expect(operationNotice("refresh", "succeeded")).toEqual({ tone: "done", title: "Checked your MyAnimeList list", detail: "Your recommendations are up to date." });
    expect(operationNotice("refresh", "failed", "Connection problem")).toEqual({ tone: "problem", title: "Checking your list didn't finish", detail: "Connection problem" });
    expect(operationNotice("sync", "cancelled")).toMatchObject({ title: "Syncing your list was stopped" });
    expect(operationNotice("refresh", "running")).toBeNull();
    expect(operationNotice("api-test", "succeeded")).toBeNull();
  });

  function Harness() {
    const shell = useShellState();
    return <Notifications notices={shell.notices} />;
  }

  it("announces an outcome seen while the page is open, never history from before it loaded", async () => {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
    vi.spyOn(api, "systemState").mockResolvedValue(SYSTEM);
    const operations = vi.spyOn(api, "operations").mockResolvedValue({ operations: [
      { id: "old", kind: "recommendation", profile_id: "p", state: "succeeded", event_count: 9 },
      { id: "now", kind: "refresh", profile_id: "p", state: "running", event_count: 1 },
    ] });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<Harness />);
    await waitFor(() => expect(operations).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
    operations.mockResolvedValue({ operations: [
      { id: "old", kind: "recommendation", profile_id: "p", state: "succeeded", event_count: 9 },
      { id: "now", kind: "refresh", profile_id: "p", state: "succeeded", event_count: 4 },
    ] });
    await act(async () => { await vi.advanceTimersByTimeAsync(3500); });
    const bell = await screen.findByRole("button", { name: "Notifications, 1 new" });
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(bell);
    const panel = screen.getByRole("region", { name: "Notifications" });
    expect(within(panel).getByText("Checked your MyAnimeList list")).toBeInTheDocument();
    expect(within(panel).queryByText(/rebuilt/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notifications" })).toHaveAttribute("aria-expanded", "true");
  });

  it("keeps at most MAX_NOTICES and says so when there is nothing", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Notifications notices={[]} />);
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    expect(screen.getByText("You're all caught up.")).toBeInTheDocument();
    expect(MAX_NOTICES).toBe(50);
    const many = Array.from({ length: 12 }, (_, id) => ({ id, at: new Date(), tone: "info" as const, title: `Notice ${id}` }));
    rerender(<Notifications notices={many} />);
    expect(screen.getByRole("button", { name: "Notifications, 12 new" })).toBeInTheDocument();
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

  it("puts the pages in a top bar, and notifications and the account top right", async () => {
    stubShell({ ...SYSTEM, needs_setup: false });
    const user = userEvent.setup();
    render(<Workspace />);
    const nav = screen.getByRole("navigation", { name: "Main navigation" });
    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(["Discover", "My Library", "Compare"]);
    expect(screen.getByRole("link", { name: "AniRec home" })).toHaveAttribute("href", "#/discover");
    // No control-panel chrome: no readout, console or build line on the page.
    expect(screen.queryByText(/ENGINE|ACTIVITY|BUILD/)).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Notifications, 1 new" })).toBeInTheDocument();

    const account = screen.getByRole("button", { name: "Account menu" });
    await user.click(account);
    const panel = screen.getByRole("region", { name: "Account" });
    expect(within(panel).getByText("Guest")).toBeInTheDocument();
    expect(within(panel).getByText("Exploring the sample library")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: "Your profile" })).toHaveAttribute("href", "#/profile");
    expect(within(panel).getByRole("link", { name: "Settings" })).toHaveAttribute("href", "#/settings");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("region", { name: "Account" })).not.toBeInTheDocument();
    expect(account).toHaveFocus();
  });

  it("tells a newcomer once, in the bell, that the sample library is safe to try", async () => {
    stubShell({ ...SYSTEM, needs_setup: false });
    const user = userEvent.setup();
    render(<Workspace />);
    await user.click(await screen.findByRole("button", { name: "Notifications, 1 new" }));
    expect(screen.getByText("You're exploring the sample library")).toBeInTheDocument();
    expect(screen.getByText("Try anything. Nothing you do here is saved.")).toBeInTheDocument();
    await user.click(document.body);
    expect(screen.getByRole("button", { name: "Notifications" })).toHaveAttribute("aria-expanded", "false");
  });

  it("shows the reader's MyAnimeList picture when the profile has one", async () => {
    stubShell({ ...SYSTEM, needs_setup: false, profile: { profile_id: "p", username: "reader" } });
    vi.spyOn(api, "profile").mockResolvedValue({ profile: { identity: { username: "reader", avatar_url: "https://cdn.myanimelist.net/images/userimages/1.jpg" } } as never });
    const { container } = render(<Workspace />);
    const button = await screen.findByRole("button", { name: "Account menu for reader" });
    await waitFor(() => expect(container.querySelector(".avatar-button img")).toHaveAttribute("src", "https://cdn.myanimelist.net/images/userimages/1.jpg"));
    expect(button).toBeInTheDocument();
  });

  it("offers first run when setup is needed, and remembers the dismissal for the session", async () => {
    stubShell(SYSTEM);
    const user = userEvent.setup();
    const { unmount } = render(<Workspace />);
    const dialog = await screen.findByRole("dialog", { name: "Welcome" });
    expect(within(dialog).getByText("No account needed. Nothing is saved.")).toBeInTheDocument();
    // Connecting an account from the web is not possible: no step offers it.
    expect(within(dialog).queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
    expect(dialog).not.toHaveTextContent(/connect|desktop|install|download/i);
    await user.click(within(dialog).getByRole("button", { name: "Look around with sample data" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    unmount();
    render(<Workspace />);
    await screen.findByRole("note");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("labels the sample library without offering to connect an account, and shows no Japanese marks", async () => {
    stubShell({ ...SYSTEM, needs_setup: false });
    const { container } = render(<Workspace />);
    const banner = await screen.findByRole("note");
    expect(banner).toHaveTextContent("You're exploring a sample library. Try anything; nothing here is saved.");
    expect(within(banner).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /connect/i })).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/[぀-ヿ一-鿿]/);
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

it("moves the build number to Settings, where only someone troubleshooting looks", async () => {
  const { SettingsPage } = await import("./SettingsPage");
  vi.spyOn(api, "settings").mockRejectedValue(new Error("offline"));
  render(<SettingsPage version="1.3.0" />);
  expect(screen.getByText("AniRec version 1.3.0")).toBeInTheDocument();
});
