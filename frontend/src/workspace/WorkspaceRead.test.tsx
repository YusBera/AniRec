import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { CompareRead, ProfileRead } from "../api/types";
import { ProfilePage } from "./ProfilePage";
import { ComparePage } from "./ComparePage";
import { Poster } from "./common";

afterEach(() => vi.restoreAllMocks());

const sample: ProfileRead = { profile: {
  is_sample: true, fingerprint: [],
  identity: { username: "anirec_sample", member_since: "", completed: 312 },
} };

it("does not substitute sample evidence for a failed local read and supports retry", async () => {
  const read = vi.spyOn(api, "profile").mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ profile: null, reason: "not-connected" });
  render(<ProfilePage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
  expect(screen.queryByRole("heading", { name: "anirec_sample" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("heading", { name: "Profile data unavailable" })).toBeInTheDocument();
  expect(screen.getByText(/profile connection is not available in this browser build/i)).toBeInTheDocument();
  expect(read.mock.calls).toEqual([[false], [false]]);
});

it("ignores a late local response after the reader explicitly selects sample", async () => {
  let resolveLocal!: (value: ProfileRead) => void;
  vi.spyOn(api, "profile").mockImplementation(isSample => isSample
    ? Promise.resolve(sample)
    : new Promise(resolve => { resolveLocal = resolve; }));
  render(<ProfilePage />);
  await userEvent.click(screen.getByRole("button", { name: "View sample profile" }));
  expect(await screen.findByRole("heading", { name: "anirec_sample" })).toBeInTheDocument();
  await act(async () => resolveLocal({ profile: null, reason: "not-connected" }));
  expect(screen.getByRole("heading", { name: "anirec_sample" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Profile data unavailable" })).not.toBeInTheDocument();
});

it("replaces a failed cover with an honest fallback and tries a new cover URL", () => {
  const { rerender } = render(<Poster title="Monster" url="https://example.test/old.jpg" />);
  fireEvent.error(screen.getByRole("img", { name: "Monster poster" }));
  expect(screen.getByRole("img", { name: "Poster unavailable for Monster" })).toBeInTheDocument();
  rerender(<Poster title="Monster" url="https://example.test/new.jpg" />);
  expect(screen.getByRole("img", { name: "Monster poster" })).toHaveAttribute("src", "https://example.test/new.jpg");
});

it("keeps the selected friend focused during loading without showing stale scores", async () => {
  const result = (username: string): CompareRead => ({ sample_names: ["NeoBalls_", "kotomi"], report: { is_sample: true, sections: [], friend: { username, match_label: "", match_score: 78 } } });
  let resolveNext!: (value: CompareRead) => void;
  vi.spyOn(api, "compare").mockImplementation((sample, name) => !sample
    ? Promise.resolve({ reason: "backend-missing", sample_names: [] })
    : name ? new Promise(resolve => { resolveNext = resolve; }) : Promise.resolve(result("NeoBalls_")));
  render(<ComparePage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Explore sample comparison" }));
  const selector = await screen.findByRole("combobox", { name: "Sample friend" });
  await user.selectOptions(selector, "kotomi");
  expect(selector).toHaveFocus();
  expect(selector).toHaveValue("kotomi");
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
  expect(screen.queryByText("78%")).not.toBeInTheDocument();
  await act(async () => resolveNext(result("kotomi")));
  expect(screen.getByRole("heading", { name: "kotomi" })).toBeInTheDocument();
  expect(selector).toHaveFocus();
});

it("saves preferences, keeps failed edits, and excludes account fields", async () => {
  const { SettingsPage } = await import("./SettingsPage");
  const initial = { adventurousness: 5, batch_size: 10, minimum_mal_score: null, default_sort: "personal-match" as const, include_hidden: false, include_nsfw: false, background_sync: false, theme: "dark" as const, gui_scale: 1, font_scale: 1, show_covers: true, username: "reader", client_id_present: true, using_defaults: false };
  vi.spyOn(api, "settings").mockResolvedValue(initial);
  const save = vi.spyOn(api, "saveSettings").mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ ...initial, adventurousness: 8 });
  render(<SettingsPage />);
  expect(await screen.findByRole("option", { name: "Personal fit" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "MAL score" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "Alphabetical" })).toBeInTheDocument();
  const user = userEvent.setup();
  const desktop = screen.getByText("Desktop-only settings").closest("details");
  expect(desktop).not.toHaveAttribute("open");
  await user.click(screen.getByText("Desktop-only settings"));
  expect(desktop).toHaveAttribute("open");
  expect(screen.getByRole("checkbox", { name: "Desktop background sync" })).toBeInTheDocument();
  const input = await screen.findByRole("spinbutton", { name: "Adventurousness (1–10)" });
  await user.clear(input); await user.type(input, "8");
  await user.click(screen.getByRole("button", { name: "Save preferences" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Your edits are kept");
  expect(input).toHaveValue(8);
  expect(save.mock.calls[0]![0]).not.toHaveProperty("username");
  expect(save.mock.calls[0]![0]).not.toHaveProperty("client_id_present");
  await user.click(screen.getByRole("button", { name: "Save preferences" }));
  expect(await screen.findByText(/Preferences saved\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save preferences" })).toBeDisabled();
});

it("shows supplied profile sections and discloses unavailable history", async () => {
  vi.spyOn(api, "profile").mockResolvedValue({ profile: { ...sample.profile!, rating_distribution: { buckets: [{ score: 9, count: 2 }] }, genres: { readings: [{ name: "Drama", watched: 2, average: 9, share: 1, titles: [{ title: "Monster", your_score: 9 }] }] } } });
  render(<ProfilePage />);
  const genre = await screen.findByText("Drama · 2 watched · 9 / 10");
  await userEvent.click(genre);
  expect(screen.getByText("Monster")).toBeVisible();
  expect(screen.getByRole("meter")).toHaveAttribute("value", "2");
  expect(screen.getByText(/Rating dates are unavailable/)).toBeInTheDocument();
});

it("submits a live comparison and renders source counts without a percentage", async () => {
  const compare = vi.spyOn(api, "compare").mockImplementation((_sample, username) => Promise.resolve(username ? { report: { is_sample: false, friend: { username, match_label: "", shared_anime: 2, both_rated: 1, total_anime: 3, match_score: null }, sections: [] }, sample_names: [] } : { reason: "username-required", sample_names: [] }));
  render(<ComparePage />);
  const user = userEvent.setup();
  await user.type(screen.getByRole("textbox", { name: "MAL username" }), "other_reader");
  await user.click(screen.getByRole("button", { name: "Compare completed lists" }));
  expect(await screen.findByRole("heading", { name: "other_reader" })).toBeInTheDocument();
  expect(compare).toHaveBeenLastCalledWith(false, "other_reader");
  expect(screen.getByText("Completed anime returned")).toBeInTheDocument();
  expect(screen.getByText("N/A")).toBeInTheDocument();
});
