import { beforeEach, describe, expect, it } from "vitest";
import { chipHref, discoverHref, readDiscoverLocation } from "./discoverUrl";

beforeEach(() => window.history.replaceState(null, "", "#/discover"));

describe("Discover URLs", () => {
  it("round trips page, multiple filters, sort, view and hidden titles", () => {
    const hash = "#/discover?genre=Drama&genre=Sci-Fi&studio=White+Fox&studio=Madhouse&minScore=7.5&sort=mal-score&page=3&view=table&hidden=show";
    const parsed = readDiscoverLocation(hash);
    expect(parsed.filters.genres).toEqual(["Drama", "Sci-Fi"]);
    expect(parsed.filters.studios).toEqual(["White Fox", "Madhouse"]);
    expect(parsed.page).toBe(2);
    expect(parsed.showHidden).toBe(true);
    expect(readDiscoverLocation(discoverHref(parsed))).toEqual(parsed);
  });

  it("ignores malformed values and keeps title language out of the URL", () => {
    const parsed = readDiscoverLocation("#/discover?page=-4&minScore=NaN&sort=unknown&view=wrong");
    expect(parsed.page).toBe(0);
    expect(parsed.filters.minimumMalScore).toBeNull();
    expect(parsed.sort).toBe("personal-match");
    expect(parsed.view).toBe("cards");
    expect(discoverHref(parsed)).not.toMatch(/title|language/);
  });

  it("makes a chip link to the first page while preserving other selections", () => {
    window.history.replaceState(null, "", "#/discover?genre=Drama&studio=Madhouse&page=4&sort=year");
    const href = chipHref("genre", "Sci-Fi");
    const parsed = readDiscoverLocation(href);
    expect(parsed.page).toBe(0);
    expect(parsed.filters.genres).toEqual(["Sci-Fi"]);
    expect(parsed.filters.studios).toEqual(["Madhouse"]);
    expect(parsed.sort).toBe("year");
  });
});
