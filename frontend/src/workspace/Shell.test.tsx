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
import { FirstRun, importProblem } from "./FirstRun";

const SYSTEM: SystemState = { profile: null, needs_setup: true, mal_client_id_present: false, password_reset_available: false, active_operations: [] };
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

  it("offers first-time setup when needed, and remembers closing it for the session", async () => {
    stubShell({ ...SYSTEM, mal_client_id_present: true });
    const user = userEvent.setup();
    const { unmount } = render(<Workspace />);
    const dialog = await screen.findByRole("dialog", { name: "Welcome to AniRec" });
    expect(within(dialog).getByText("your personal anime recommender")).toBeInTheDocument();
    // Never a Client ID, a MyAnimeList login or a desktop app (D-017). The
    // only sign-in is to an AniRec account (D-021).
    expect(dialog).not.toHaveTextContent(/client id|log ?in|desktop|install|download/i);
    expect(within(dialog).getByRole("button", { name: "Sign in" }).closest("p")).toHaveTextContent("Already have an account? Sign in");
    await user.click(within(dialog).getByRole("button", { name: "Just look around" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    unmount();
    render(<Workspace />);
    await screen.findByRole("note");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("does not open setup on its own for a reader who already has a profile", async () => {
    stubShell({ ...SYSTEM, mal_client_id_present: true, profile: { profile_id: "p", username: "reader" } });
    vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
    render(<Workspace />);
    await screen.findByRole("button", { name: "Account menu for reader" });
    await act(async () => { await Promise.resolve(); });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("tells the reader the list is being read, without promising what follows", async () => {
    stubShell({ ...SYSTEM, mal_client_id_present: true });
    vi.spyOn(api, "importMalProfile").mockResolvedValue({ profile: { profile_id: "p", username: "reader_01" }, reason: null });
    const user = userEvent.setup();
    render(<Workspace />);
    const dialog = await screen.findByRole("dialog", { name: "Welcome to AniRec" });
    await user.type(within(dialog).getByRole("textbox", { name: "MyAnimeList" }), "reader_01");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /^Notifications/ }));
    expect(screen.getByText("Added reader_01's MyAnimeList list")).toBeInTheDocument();
    expect(screen.getByText("AniRec is reading it now.")).toBeInTheDocument();
  });

  it("lets a guest reopen setup from the account menu", async () => {
    stubShell({ ...SYSTEM, needs_setup: false, mal_client_id_present: true });
    const user = userEvent.setup();
    render(<Workspace />);
    await user.click(await screen.findByRole("button", { name: "Account menu" }));
    await user.click(screen.getByRole("button", { name: "Set up your profile" }));
    expect(await screen.findByRole("dialog", { name: "Welcome to AniRec" })).toBeInTheDocument();
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

describe("first-time setup (D-020)", () => {
  const renderSetup = (clientIdPresent = true) => {
    const onImported = vi.fn();
    const onClose = vi.fn();
    render(<FirstRun clientIdPresent={clientIdPresent} onImported={onImported} onClose={onClose} />);
    return { onImported, onClose, dialog: screen.getByRole("dialog", { name: "Welcome to AniRec" }) };
  };

  it("lays out MyAnimeList as a field, AniList and AniDB as coming soon, and the newcomer path as not active yet", () => {
    const { dialog } = renderSetup();
    expect(within(dialog).getByRole("textbox", { name: "MyAnimeList" })).toHaveAttribute("placeholder", "Your username");
    expect(within(dialog).getAllByText("Coming soon")).toHaveLength(2);
    expect(within(dialog).queryByRole("textbox", { name: /AniList|AniDB/ })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "I'm new to anime" })).toHaveAttribute("aria-disabled", "true");
    expect(within(dialog).getByRole("button", { name: "Just look around" })).toBeInTheDocument();
  });

  it("starts from a public list: sends only the username, closes, and hands the new profile on", async () => {
    const importer = vi.spyOn(api, "importMalProfile").mockResolvedValue({ profile: { profile_id: "p", username: "reader_01" }, reason: null });
    const { onImported, onClose, dialog } = renderSetup();
    const user = userEvent.setup();
    await user.type(within(dialog).getByRole("textbox", { name: "MyAnimeList" }), "reader_01");
    await user.click(within(dialog).getByRole("button", { name: "Continue with MyAnimeList" }));
    expect(importer).toHaveBeenCalledWith("reader_01");
    await waitFor(() => expect(onImported).toHaveBeenCalledWith({ profile_id: "p", username: "reader_01" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("says in plain words why a list could not be read, and keeps the reader in the field", async () => {
    vi.spyOn(api, "importMalProfile").mockResolvedValue({ profile: null, reason: "private-list" });
    const { onImported, dialog } = renderSetup();
    const user = userEvent.setup();
    const field = within(dialog).getByRole("textbox", { name: "MyAnimeList" });
    await user.type(field, "shy_reader");
    await user.keyboard("{Enter}");
    const live = within(dialog).getByRole("status");
    await waitFor(() => expect(live).toHaveTextContent("shy_reader's anime list isn't public, so AniRec can't read it."));
    // One live region throughout, so the announcement is not lost to a role swap.
    expect(within(dialog).getByRole("status")).toBe(live);
    expect(field).toHaveFocus();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(onImported).not.toHaveBeenCalled();
  });

  it("keeps the button's visible words inside its accessible name while it works", async () => {
    let finish!: (value: { profile: null; reason: string }) => void;
    vi.spyOn(api, "importMalProfile").mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const { dialog } = renderSetup();
    const user = userEvent.setup();
    await user.type(within(dialog).getByRole("textbox", { name: "MyAnimeList" }), "reader_01");
    await user.keyboard("{Enter}");
    const button = within(dialog).getByRole("button", { name: /with MyAnimeList/ });
    const visible = [...button.childNodes].filter((node) => !(node instanceof HTMLElement && node.classList.contains("visually-hidden")))
      .map((node) => node.textContent).join("").trim();
    expect(visible).toBe("Reading…");
    expect(button).toHaveAccessibleName(expect.stringContaining(visible));
    await act(async () => finish({ profile: null, reason: "network" }));
  });

  it("does nothing when the newcomer path is pressed before it exists", async () => {
    const importer = vi.spyOn(api, "importMalProfile");
    const { onClose, dialog } = renderSetup();
    await userEvent.setup().click(within(dialog).getByRole("button", { name: "I'm new to anime" }));
    expect(importer).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("says so when this installation cannot read MyAnimeList lists, instead of a field that fails", () => {
    const { dialog } = renderSetup(false);
    expect(within(dialog).getByRole("textbox", { name: "MyAnimeList" })).toBeDisabled();
    expect(dialog).toHaveTextContent("MyAnimeList import isn't set up for this AniRec installation yet.");
  });

  it("words every reason the service can give", () => {
    for (const reason of ["invalid-username", "client-id-required", "user-not-found", "private-list", "installation-refused", "rate-limited", "network", "unavailable"]) {
      expect(importProblem(reason, "x")).not.toMatch(/undefined|reason|HTTP/);
    }
    // MyAnimeList refusing the installation is not the reader's list or connection.
    expect(importProblem("installation-refused", "x")).not.toBe(importProblem("unavailable", "x"));
    expect(importProblem("installation-refused", "x")).not.toMatch(/public|connection|spelling/i);
    expect(importProblem("user-not-found", "nobody_here")).toContain("nobody_here");
  });
});


describe("accounts (D-021)", () => {
  function stubShell(system: SystemState) {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
    vi.spyOn(api, "systemState").mockResolvedValue(system);
    vi.spyOn(api, "operations").mockResolvedValue({ operations: [] });
    vi.spyOn(api, "feed").mockResolvedValue(SAMPLE_FEED);
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  }
  const GUEST = { kind: "guest" as const, email: null, has_import: true, installation_owner: false };
  const READER = { kind: "registered" as const, email: "reader@example.com", has_import: true, installation_owner: false };
  const WITH_LIST = { ...SYSTEM, needs_setup: false, profile: { profile_id: "imp_1", username: "reader_01", kept_on_delete: false } };

  it("offers a guest Create account and Sign in, and a registered reader their email and Sign out", async () => {
    vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
    stubShell({ ...WITH_LIST, account: GUEST });
    const user = userEvent.setup();
    const { unmount } = render(<Workspace />);
    await user.click(await screen.findByRole("button", { name: "Account menu for reader_01" }));
    let panel = screen.getByRole("region", { name: "Account" });
    expect(within(panel).getByRole("button", { name: "Create account" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
    unmount();

    stubShell({ ...WITH_LIST, account: READER });
    render(<Workspace />);
    await user.click(await screen.findByRole("button", { name: "Account menu for reader_01" }));
    panel = screen.getByRole("region", { name: "Account" });
    expect(within(panel).getByText("reader@example.com")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: "Create account" })).not.toBeInTheDocument();
  });

  it("reminds a guest with a list to create an account, once per session if dismissed", async () => {
    vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
    stubShell({ ...WITH_LIST, account: GUEST });
    const user = userEvent.setup();
    const { unmount } = render(<Workspace />);
    const prompt = await screen.findByRole("region", { name: "Keep your list" });
    expect(prompt).toHaveTextContent("Create an account so you don't lose your Watch Later.");
    await user.click(within(prompt).getByRole("button", { name: "Not now" }));
    expect(screen.queryByRole("region", { name: "Keep your list" })).not.toBeInTheDocument();
    unmount();
    render(<Workspace />);
    await screen.findByRole("button", { name: "Account menu for reader_01" });
    expect(screen.queryByRole("region", { name: "Keep your list" })).not.toBeInTheDocument();
  });

  it("never reminds a registered reader", async () => {
    vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
    stubShell({ ...WITH_LIST, account: READER });
    render(<Workspace />);
    await screen.findByRole("button", { name: "Account menu for reader_01" });
    expect(screen.queryByRole("region", { name: "Keep your list" })).not.toBeInTheDocument();
  });

  it("creates the account from the reminder and reloads the pages for it", async () => {
    vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
    stubShell({ ...WITH_LIST, account: GUEST });
    const register = vi.spyOn(api, "register").mockResolvedValue({ account: { ...READER }, reason: null, moved_imports: 0 });
    const user = userEvent.setup();
    render(<Workspace />);
    const feedCalls = (api.feed as unknown as { mock: { calls: unknown[] } }).mock.calls.length;
    await user.click(within(await screen.findByRole("region", { name: "Keep your list" })).getByRole("button", { name: "Create account" }));
    const dialog = screen.getByRole("dialog", { name: "Create your account" });
    await user.type(within(dialog).getByLabelText("Email"), "reader@example.com");
    await user.type(within(dialog).getByLabelText("Password"), "a long password");
    await user.click(within(dialog).getByRole("button", { name: "Create account" }));
    expect(register).toHaveBeenCalledWith("reader@example.com", "a long password");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect((api.feed as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBeGreaterThan(feedCalls));
  });

  it("opens sign-in from first-time setup for a returning reader", async () => {
    stubShell({ ...SYSTEM, mal_client_id_present: true });
    const user = userEvent.setup();
    render(<Workspace />);
    const setup = await screen.findByRole("dialog", { name: "Welcome to AniRec" });
    await user.click(within(setup).getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("dialog", { name: "Welcome back" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Welcome to AniRec" })).not.toBeInTheDocument();
  });
});

describe("the account dialog (D-021)", () => {
  it("says in words why signing in failed, keeps the password private, and can show it", async () => {
    const { AccountDialog } = await import("./AccountDialog");
    vi.spyOn(api, "signIn").mockResolvedValue({ account: null, reason: "wrong-credentials", moved_imports: 0 });
    const onDone = vi.fn();
    render(<AccountDialog mode="sign-in" onDone={onDone} onClose={vi.fn()} />);
    const dialog = screen.getByRole("dialog", { name: "Welcome back" });
    const user = userEvent.setup();
    const email = within(dialog).getByLabelText("Email");
    const password = within(dialog).getByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    await user.click(within(dialog).getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    await user.type(email, "reader@example.com");
    await user.type(password, "not the password");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(within(dialog).getByRole("status")).toHaveTextContent("That email and password don't match an account."));
    expect(email).toHaveFocus();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("switches between creating an account and signing in", async () => {
    const { AccountDialog } = await import("./AccountDialog");
    render(<AccountDialog mode="register" onDone={vi.fn()} onClose={vi.fn()} />);
    const user = userEvent.setup();
    expect(screen.getByLabelText("Password")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByText("At least 8 characters.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("dialog", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("words every reason the service can give, without technical terms", async () => {
    const { accountProblem } = await import("./AccountDialog");
    for (const reason of ["invalid-email", "weak-password", "password-too-long", "email-taken", "wrong-credentials", "too-many-attempts", "already-signed-in", "busy", "unavailable"]) {
      expect(accountProblem(reason)).not.toMatch(/undefined|reason|HTTP|session|token|cookie/i);
    }
    expect(accountProblem("email-taken")).not.toBe(accountProblem("unavailable"));
  });
});

it("shows the desktop settings read-only, with the reason, to anyone but the owner", async () => {
  const { SettingsPage } = await import("./SettingsPage");
  vi.spyOn(api, "settings").mockResolvedValue({
    adventurousness: 5, batch_size: 10, minimum_mal_score: null, default_sort: "personal-match", include_hidden: false,
    include_nsfw: false, background_sync: false, theme: "dark", gui_scale: 1, font_scale: 1, show_covers: true,
    username: "reader", client_id_present: true, using_defaults: false, can_edit: false, can_edit_preferences: false,
  });
  render(<SettingsPage />);
  expect(await screen.findByText("Only the owner of this AniRec installation can change the desktop app's settings.")).toBeInTheDocument();
  expect(screen.getByText("Add your MyAnimeList list or create an account to save your own preferences.")).toBeInTheDocument();
  expect(screen.getByRole("slider", { name: "Adventurousness (1–10)" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Save desktop settings" })).toBeDisabled();
});

describe("Settings → ACCOUNT (D-021)", () => {
  const SETTINGS = {
    adventurousness: 5, batch_size: 10, minimum_mal_score: null, default_sort: "personal-match" as const, include_hidden: false,
    include_nsfw: false, background_sync: false, theme: "dark" as const, gui_scale: 1, font_scale: 1, show_covers: true,
    username: "reader_01", client_id_present: true, using_defaults: false, can_edit: false, can_edit_preferences: true,
  };
  const READER = { kind: "registered" as const, email: "reader@example.com", has_import: true, installation_owner: false };

  it("changes the password and says what it did", async () => {
    const { SettingsPage } = await import("./SettingsPage");
    vi.spyOn(api, "settings").mockResolvedValue(SETTINGS);
    const change = vi.spyOn(api, "changePassword").mockResolvedValue({ account: READER, reason: null, moved_imports: 0 });
    const onAccount = vi.fn();
    render(<SettingsPage account={READER} onAccount={onAccount} />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Current password"), "a long password");
    await user.type(screen.getByLabelText("New password"), "a new long password");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(change).toHaveBeenCalledWith("a long password", "a new long password");
    expect(await screen.findByText(/Password changed\./)).toBeInTheDocument();
    expect(onAccount).toHaveBeenCalledWith("password-changed");
    expect(screen.getByLabelText("Current password")).toHaveValue("");
  });

  it("says in words when the data can't be downloaded", async () => {
    const { SettingsPage } = await import("./SettingsPage");
    const { AniRecApiError } = await import("../api/client");
    vi.spyOn(api, "settings").mockResolvedValue(SETTINGS);
    vi.spyOn(api, "exportAccount").mockRejectedValue(new AniRecApiError({ code: "x", title: "x", description: "", solution: "", retryable: false }, 429));
    render(<SettingsPage account={READER} />);
    await userEvent.setup().click(await screen.findByRole("button", { name: "Download my data" }));
    expect(await screen.findByText("You've downloaded your data several times this hour. Try again later.")).toBeInTheDocument();
  });

  it("separates the lists deleted from the ones kept for the desktop app, and never guesses", async () => {
    const { SettingsPage } = await import("./SettingsPage");
    vi.spyOn(api, "settings").mockResolvedValue(SETTINGS);
    const imports = vi.spyOn(api, "imports")
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ imports: [
        { profile_id: "imp_1", username: "reader_01", kept_on_delete: false },
        { profile_id: "mal-123", username: "desktop_reader", kept_on_delete: true },
      ], active_profile_id: "imp_1", reason: null });
    render(<SettingsPage account={READER} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete account" }));
    const dialog = screen.getByRole("dialog", { name: "Delete your account?" });
    expect(await within(dialog).findByText(/Your lists couldn't be read/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Delete my account" })).toBeDisabled();
    await user.click(within(dialog).getByRole("button", { name: "Try again" }));
    expect(await within(dialog).findByText("reader_01's list")).toBeInTheDocument();
    expect(within(dialog).getByText("Kept, because the desktop app uses it:")).toBeInTheDocument();
    expect(within(dialog).getByText("desktop_reader's list")).toBeInTheDocument();
    expect(imports).toHaveBeenCalledTimes(2);
  });

  it("names every list before deleting, asks for the password, and reports a refusal in words", async () => {
    const { SettingsPage } = await import("./SettingsPage");
    vi.spyOn(api, "settings").mockResolvedValue(SETTINGS);
    vi.spyOn(api, "imports").mockResolvedValue({ imports: [
      { profile_id: "imp_1", username: "reader_01", kept_on_delete: false }, { profile_id: "imp_2", username: "guest_list", kept_on_delete: false },
    ], active_profile_id: "imp_1", reason: null });
    const remove = vi.spyOn(api, "deleteAccount")
      .mockResolvedValueOnce({ account: null, reason: "wrong-credentials", moved_imports: 0 })
      .mockResolvedValueOnce({ account: null, reason: null, moved_imports: 0 });
    const onAccount = vi.fn();
    render(<SettingsPage account={READER} onAccount={onAccount} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Delete account" }));
    const dialog = screen.getByRole("dialog", { name: "Delete your account?" });
    expect(await within(dialog).findByText("reader_01's list")).toBeInTheDocument();
    expect(within(dialog).getByText("guest_list's list")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("Your password"), "wrong one");
    await user.click(within(dialog).getByRole("button", { name: "Delete my account" }));
    expect(await within(dialog).findByText("That password isn't right.")).toBeInTheDocument();
    expect(onAccount).not.toHaveBeenCalled();
    await user.clear(within(dialog).getByLabelText("Your password"));
    await user.type(within(dialog).getByLabelText("Your password"), "a long password");
    await user.click(within(dialog).getByRole("button", { name: "Delete my account" }));
    expect(remove).toHaveBeenLastCalledWith("a long password");
    await waitFor(() => expect(onAccount).toHaveBeenCalledWith("deleted"));
  });

  it("lets a guest delete their data without a password", async () => {
    const { SettingsPage } = await import("./SettingsPage");
    vi.spyOn(api, "settings").mockResolvedValue(SETTINGS);
    vi.spyOn(api, "imports").mockResolvedValue({ imports: [{ profile_id: "imp_1", username: "reader_01", kept_on_delete: false }], active_profile_id: "imp_1", reason: null });
    const remove = vi.spyOn(api, "deleteAccount").mockResolvedValue({ account: null, reason: null, moved_imports: 0 });
    render(<SettingsPage account={{ kind: "guest", email: null, has_import: true, installation_owner: false }} />);
    const user = userEvent.setup();
    expect(await screen.findByText(/You're using AniRec as a guest/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete my data" }));
    const dialog = screen.getByRole("dialog", { name: "Delete your data?" });
    await within(dialog).findByText("reader_01's list");
    expect(within(dialog).queryByLabelText("Your password")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Delete my data" }));
    expect(remove).toHaveBeenCalledWith(null);
  });
});

it("forgets the previous reader's notifications when someone signs out (D-021)", async () => {
  vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
  vi.spyOn(api, "systemState").mockResolvedValue({ ...SYSTEM, needs_setup: false, profile: { profile_id: "imp_1", username: "reader_01" },
    account: { kind: "registered", email: "reader@example.com", has_import: true, installation_owner: false } });
  vi.spyOn(api, "operations").mockResolvedValue({ operations: [] });
  vi.spyOn(api, "feed").mockResolvedValue(SAMPLE_FEED);
  vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
  vi.spyOn(api, "signOut").mockResolvedValue({ account: null, reason: null, moved_imports: 0 });
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  const user = userEvent.setup();
  render(<Workspace />);
  // The sample library notice stands in for anything the reader was told.
  await user.click(await screen.findByRole("button", { name: "Notifications, 1 new" }));
  expect(screen.getByText("You're exploring the sample library")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /^Account menu/ }));
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  await user.click(await screen.findByRole("button", { name: /^Notifications/ }));
  await waitFor(() => expect(screen.getByText("Signed out")).toBeInTheDocument());
  expect(screen.queryByText("You're exploring the sample library")).not.toBeInTheDocument();
});

it("says where a guest's list went when they sign in to an account that already has one (D-021)", async () => {
  vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
  vi.spyOn(api, "systemState").mockResolvedValue({ ...SYSTEM, needs_setup: false, profile: { profile_id: "imp_1", username: "reader_01" },
    account: { kind: "guest", email: null, has_import: true, installation_owner: false } });
  vi.spyOn(api, "operations").mockResolvedValue({ operations: [] });
  vi.spyOn(api, "feed").mockResolvedValue(SAMPLE_FEED);
  vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
  vi.spyOn(api, "signIn").mockResolvedValue({ account: { kind: "registered", email: "reader@example.com", has_import: true, installation_owner: false }, reason: null, moved_imports: 1 });
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  const user = userEvent.setup();
  render(<Workspace />);
  await user.click(await screen.findByRole("button", { name: /^Account menu/ }));
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  const dialog = await screen.findByRole("dialog", { name: "Welcome back" });
  await user.type(within(dialog).getByLabelText("Email"), "reader@example.com");
  await user.type(within(dialog).getByLabelText("Password"), "a long password");
  await user.keyboard("{Enter}");
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  await user.click(screen.getByRole("button", { name: /^Notifications/ }));
  expect(screen.getByText(/The list you added before signing in is saved to your account. Switch to it from the account menu/)).toBeInTheDocument();
});

describe("switching lists (D-021)", () => {
  const READER_STATE: SystemState = { ...SYSTEM, needs_setup: false, profile: { profile_id: "imp_1", username: "reader_01" },
    account: { kind: "registered", email: "reader@example.com", has_import: true, installation_owner: false } };
  function stub() {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
    vi.spyOn(api, "systemState").mockResolvedValue(READER_STATE);
    vi.spyOn(api, "operations").mockResolvedValue({ operations: [] });
    vi.spyOn(api, "feed").mockResolvedValue(SAMPLE_FEED);
    vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  }

  it("lists an account's own lists, marks the one shown, and switches", async () => {
    stub();
    vi.spyOn(api, "imports").mockResolvedValue({ imports: [
      { profile_id: "imp_1", username: "reader_01", kept_on_delete: false }, { profile_id: "imp_2", username: "guest_list", kept_on_delete: false },
    ], active_profile_id: "imp_1", reason: null });
    const choose = vi.spyOn(api, "chooseImport").mockResolvedValue({ imports: [], active_profile_id: "imp_2", reason: null });
    const user = userEvent.setup();
    render(<Workspace />);
    const feedCalls = (api.feed as unknown as { mock: { calls: unknown[] } }).mock.calls.length;
    await user.click(await screen.findByRole("button", { name: "Account menu for reader_01" }));
    const panel = screen.getByRole("region", { name: "Account" });
    expect(await within(panel).findByRole("heading", { name: "Your lists" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "reader_01, shown now" })).toHaveAttribute("aria-current", "true");
    expect(within(panel).getByRole("button", { name: "Add another list" })).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Show guest_list" }));
    expect(choose).toHaveBeenCalledWith("imp_2");
    await waitFor(() => expect((api.feed as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBeGreaterThan(feedCalls));
    expect(document.getElementById("workspace-content")).toHaveFocus();
    await user.click(screen.getByRole("button", { name: /^Notifications/ }));
    expect(screen.getByText("Showing guest_list's list")).toBeInTheDocument();
  });

  it("shows no switcher for an account with one list", async () => {
    stub();
    vi.spyOn(api, "imports").mockResolvedValue({ imports: [{ profile_id: "imp_1", username: "reader_01", kept_on_delete: false }], active_profile_id: "imp_1", reason: null });
    const user = userEvent.setup();
    render(<Workspace />);
    await user.click(await screen.findByRole("button", { name: "Account menu for reader_01" }));
    await waitFor(() => expect(api.imports).toHaveBeenCalled());
    expect(screen.queryByRole("heading", { name: "Your lists" })).not.toBeInTheDocument();
  });
});

it("says in words when Compare's MyAnimeList lookups are limited", async () => {
  vi.spyOn(api, "compare").mockResolvedValue({ report: null, reason: "busy", sample_names: [] });
  render(<ComparePage />);
  const user = userEvent.setup();
  await user.type(screen.getByRole("textbox", { name: /MAL username/ }), "friend");
  await user.click(screen.getByRole("button", { name: "Compare your anime list with this profile" }));
  expect(await screen.findByText("Too many lookups for now")).toBeInTheDocument();
});

describe("password reset by email (D-021, phase 5)", () => {
  const READER = { kind: "registered" as const, email: "reader@example.com", has_import: true, installation_owner: false };
  function stubShell(system: SystemState) {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
    vi.spyOn(api, "systemState").mockResolvedValue(system);
    vi.spyOn(api, "operations").mockResolvedValue({ operations: [] });
    vi.spyOn(api, "feed").mockResolvedValue(SAMPLE_FEED);
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  }
  afterEach(() => { history.replaceState(null, "", location.pathname); });

  it("asks for a link from the sign-in dialog and answers the same for every email", async () => {
    const { AccountDialog } = await import("./AccountDialog");
    const ask = vi.spyOn(api, "requestPasswordReset").mockResolvedValue({ reason: null });
    render(<AccountDialog mode="sign-in" resetAvailable onDone={vi.fn()} onClose={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Forgot your password?" }));
    const dialog = screen.getByRole("dialog", { name: "Reset your password" });
    const email = within(dialog).getByLabelText("Email");
    expect(email).toHaveFocus();
    expect(within(dialog).queryByLabelText("Password")).not.toBeInTheDocument();
    await user.type(email, "reader@example.com");
    await user.click(within(dialog).getByRole("button", { name: "Email me a link" }));
    expect(ask).toHaveBeenCalledWith("reader@example.com");
    await waitFor(() => expect(within(dialog).getByRole("status")).toHaveTextContent(
      "If an account uses that email, a link to reset its password is on its way. It works for 30 minutes."));
    await user.click(within(dialog).getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("dialog", { name: "Welcome back" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveFocus();
  });

  it("says in words that reset isn't available when this AniRec can't send email", async () => {
    const { AccountDialog } = await import("./AccountDialog");
    const ask = vi.spyOn(api, "requestPasswordReset");
    const { unmount } = render(<AccountDialog mode="sign-in" onDone={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByText(/isn't set up to send email, so a password can't be reset here/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Forgot your password?" })).not.toBeInTheDocument();
    unmount();
    render(<AccountDialog mode="reset" onDone={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: "Reset your password" })).toHaveTextContent(/isn't set up to send email/);
    expect(screen.queryByRole("button", { name: "Email me a link" })).not.toBeInTheDocument();
    expect(ask).not.toHaveBeenCalled();
  });

  it("words every reason a reset can be refused, without technical terms", async () => {
    const { resetProblem } = await import("./AccountDialog");
    for (const reason of ["reset-unavailable", "invalid-email", "too-many-attempts", "busy", "invalid-token", "weak-password", "password-too-long", "unavailable"]) {
      expect(resetProblem(reason)).not.toMatch(/undefined|reason|HTTP|session|token|cookie|SMTP/i);
    }
    expect(resetProblem("invalid-token")).toMatch(/expired or has already been used/);
  });

  it("emails a reset link to a registered reader from Settings", async () => {
    const { AccountSection } = await import("./AccountSection");
    const ask = vi.spyOn(api, "requestPasswordReset").mockResolvedValue({ reason: null });
    const { unmount } = render(<AccountSection account={READER} resetAvailable />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Email me a reset link" }));
    expect(ask).toHaveBeenCalledWith("reader@example.com");
    expect(await screen.findByText(/A reset link is on its way to reader@example.com/)).toBeInTheDocument();
    unmount();
    render(<AccountSection account={READER} />);
    expect(screen.getByText(/isn't set up to send email, so it can't send you a reset link/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Email me a reset link" })).not.toBeInTheDocument();
  });

  it("opens the reset page from the emailed link, takes the token out of the address, and never opens setup over it", async () => {
    stubShell({ ...SYSTEM, needs_setup: true, password_reset_available: true });
    const confirm = vi.spyOn(api, "confirmPasswordReset").mockResolvedValue({ reason: null });
    history.replaceState(null, "", "#/reset-password?token=emailed-token");
    render(<Workspace />);
    const heading = await screen.findByRole("heading", { level: 1, name: "Choose a new password" });
    expect(location.hash).toBe("#/reset-password");
    expect(location.href).not.toContain("emailed-token");
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.queryByRole("dialog", { name: "Welcome to AniRec" })).not.toBeInTheDocument();
    const user = userEvent.setup();
    const password = screen.getByLabelText("New password");
    expect(password).toHaveAttribute("autocomplete", "new-password");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAccessibleDescription(/At least 8 characters/);
    await user.type(password, "a brand new password{Enter}");
    expect(confirm).toHaveBeenCalledWith("emailed-token", "a brand new password");
    expect(await screen.findByText(/Your password was changed/)).toHaveTextContent(/signed out everywhere/);
    const signIn = screen.getByRole("button", { name: "Sign in" });
    expect(signIn).toHaveFocus();
    await user.click(signIn);
    expect(screen.getByRole("dialog", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("says a used or expired link can't be used and offers a new one", async () => {
    stubShell({ ...SYSTEM, needs_setup: false, password_reset_available: true });
    vi.spyOn(api, "confirmPasswordReset").mockResolvedValue({ reason: "invalid-token" });
    history.replaceState(null, "", "#/reset-password?token=spent");
    render(<Workspace />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("New password"), "a brand new password");
    await user.click(screen.getByRole("button", { name: "Set new password" }));
    expect(await screen.findByText("This link has expired or has already been used. Ask for a new one.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Email me a new link" }));
    expect(screen.getByRole("dialog", { name: "Reset your password" })).toBeInTheDocument();
  });

  it("closes first-time setup when a reset link opens in a tab that shows it", async () => {
    stubShell({ ...SYSTEM, needs_setup: true, password_reset_available: true });
    history.replaceState(null, "", "#/discover");
    render(<Workspace />);
    expect(await screen.findByRole("dialog", { name: "Welcome to AniRec" })).toBeInTheDocument();
    await act(async () => {
      history.replaceState(null, "", "#/reset-password?token=later");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Welcome to AniRec" })).not.toBeInTheDocument());
    expect(screen.getByLabelText("New password")).toBeInTheDocument();
    expect(location.hash).toBe("#/reset-password");
  });

  it("words a refusal to set the password for what the reader just did", async () => {
    stubShell({ ...SYSTEM, needs_setup: false, password_reset_available: true });
    vi.spyOn(api, "confirmPasswordReset").mockResolvedValue({ reason: "too-many-attempts" });
    history.replaceState(null, "", "#/reset-password?token=t");
    render(<Workspace />);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("New password"), "a brand new password{Enter}");
    expect(await screen.findByText("Too many attempts. Wait a minute, then try again.")).toBeInTheDocument();
  });

  it("says so when the link is incomplete, instead of a form that can't work", async () => {
    stubShell({ ...SYSTEM, needs_setup: false, password_reset_available: true });
    const confirm = vi.spyOn(api, "confirmPasswordReset");
    history.replaceState(null, "", "#/reset-password?from=mail");
    render(<Workspace />);
    expect(await screen.findByText(/This link is incomplete/)).toBeInTheDocument();
    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Email me a new link" })).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
  });
});

describe("follow-ups from the first real-data run", () => {
  const READER = { kind: "registered" as const, email: "reader@example.com", has_import: true, installation_owner: true };
  function stubShell(system: SystemState) {
    vi.spyOn(api, "health").mockResolvedValue({ status: "ok", version: "1.3.0" });
    vi.spyOn(api, "systemState").mockResolvedValue(system);
    vi.spyOn(api, "operations").mockResolvedValue({ operations: [] });
    vi.spyOn(api, "feed").mockResolvedValue(SAMPLE_FEED);
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  }

  it("never offers Sign in to a signed-in reader adding another list", async () => {
    vi.spyOn(api, "profile").mockResolvedValue({ profile: null } as never);
    stubShell({ ...SYSTEM, needs_setup: false, mal_client_id_present: true, account: READER,
      profile: { profile_id: "imp_1", username: "reader_01", kept_on_delete: false } } as SystemState);
    const user = userEvent.setup();
    render(<Workspace />);
    await user.click(await screen.findByRole("button", { name: "Account menu for reader_01" }));
    await user.click(screen.getByRole("button", { name: "Add another list" }));
    const setup = await screen.findByRole("dialog", { name: "Welcome to AniRec" });
    expect(within(setup).queryByRole("button", { name: "Sign in" })).not.toBeInTheDocument();
    expect(within(setup).queryByText(/Already have an account/)).not.toBeInTheDocument();
  });

  it("says in words when MyAnimeList turned down this AniRec, without sending the reader to reconnect", async () => {
    vi.spyOn(api, "compare").mockResolvedValue({ report: null, reason: "installation-refused", sample_names: [] } as never);
    render(<ComparePage />);
    expect(await screen.findByText("MyAnimeList turned down this AniRec")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/reconnect/i);
  });

  it("ships every icon inside the page, so a menu never waits for one", async () => {
    const { ICONS } = await import("../assets/Icon");
    for (const [name, source] of Object.entries(ICONS)) {
      expect(source, name).toMatch(/^data:image\/svg\+xml,/);
    }
  });

  it("lets a password manager recognise and save the new account", async () => {
    const { AccountDialog } = await import("./AccountDialog");
    vi.spyOn(api, "register").mockResolvedValue({ account: READER, reason: null, moved_imports: 0 });
    let atClose = "";
    render(<AccountDialog mode="register" onDone={() => { atClose = (document.querySelector("input[name=password]") as HTMLInputElement | null)?.value ?? "gone"; }} onClose={vi.fn()} />);
    const email = screen.getByLabelText("Email");
    const password = screen.getByLabelText("Password");
    expect(email).toHaveAttribute("name", "email");
    expect(email).toHaveAttribute("autocomplete", "username");
    expect(password).toHaveAttribute("name", "password");
    expect(password).toHaveAttribute("autocomplete", "new-password");
    const user = userEvent.setup();
    await user.type(email, "reader@example.com");
    await user.type(password, "a long password{Enter}");
    await waitFor(() => expect(atClose).not.toBe(""));
    // Still filled when the form goes away: managers read it then.
    expect(atClose).toBe("a long password");
  });
});
