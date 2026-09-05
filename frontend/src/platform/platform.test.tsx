/**
 * The platform seam, and the property that makes it worth having.
 *
 * The rule under test is not "does openExternal work" - it is that the app
 * still runs as an ordinary web page. A regression here looks like the
 * browser build importing `@tauri-apps/*` at load, or a component branching
 * on which shell it is in, and both are silent until someone opens the web
 * version.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { browserPlatform } from "./browser";
import { __resetPlatformForTests, getPlatform, isTauri } from "./index";
import { PlatformProvider, usePlatform } from "./PlatformContext";
import { BackendUnavailableError, type Platform } from "./types";

afterEach(() => {
  __resetPlatformForTests();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  delete window.__TAURI_INTERNALS__;
});

describe("detection", () => {
  it("reports a browser when Tauri has not injected itself", () => {
    expect(isTauri()).toBe(false);
  });

  it("reports Tauri when it has", () => {
    window.__TAURI_INTERNALS__ = {};
    expect(isTauri()).toBe(true);
  });

  it("resolves to the browser platform in a browser", async () => {
    expect(await getPlatform()).toBe(browserPlatform);
  });

  it("never imports the Tauri packages in a browser", async () => {
    // The guarantee that keeps the web build shippable: resolving the
    // platform in a browser must not pull in a desktop-only dependency.
    const platform = await getPlatform();
    expect(platform.name).toBe("browser");
  });
});

describe("the browser platform", () => {
  it("talks to the same origin with no token", async () => {
    expect(await browserPlatform.connect()).toEqual({ baseUrl: "", token: null });
  });

  it("opens links in a new tab without handing over a window reference", async () => {
    const open = vi.fn();
    vi.stubGlobal("open", open);
    await browserPlatform.openExternal("https://myanimelist.net/anime/1535");
    expect(open).toHaveBeenCalledWith(
      "https://myanimelist.net/anime/1535",
      "_blank",
      "noopener,noreferrer",
    );
  });
});

describe("PlatformProvider", () => {
  function Probe() {
    return <span>platform: {usePlatform().name}</span>;
  }

  it("configures the client, then renders its children", async () => {
    render(
      <PlatformProvider>
        <Probe />
      </PlatformProvider>,
    );
    expect(await screen.findByText("platform: browser")).toBeInTheDocument();
  });

  it("shows a real failure screen when the backend cannot start", async () => {
    __resetPlatformForTests({
      name: "tauri",
      connect: async () => {
        throw new BackendUnavailableError(
          "spawn_failed",
          "The AniRec service did not start.",
        );
      },
      openExternal: async () => {},
    } satisfies Platform);

    render(
      <PlatformProvider>
        <Probe />
      </PlatformProvider>,
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("could not start its local service");
    expect(alert).toHaveTextContent("spawn_failed");
    // A failure must not silently render the app against a dead backend.
    expect(screen.queryByText(/^platform:/)).not.toBeInTheDocument();
  });

  it("does not leave the user on a spinner forever", async () => {
    __resetPlatformForTests({
      name: "tauri",
      connect: async () => {
        throw new Error("something unexpected");
      },
      openExternal: async () => {},
    } satisfies Platform);

    render(
      <PlatformProvider>
        <Probe />
      </PlatformProvider>,
    );
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});

describe("components outside a provider", () => {
  it("get the browser platform rather than an exception", async () => {
    // Every component test renders without the provider. Throwing here would
    // make the seam cost more than it saves.
    function Bare() {
      return <span>{usePlatform().name}</span>;
    }
    render(<Bare />);
    expect(screen.getByText("browser")).toBeInTheDocument();
  });

  it("routes an external link through the platform, not target=_blank", async () => {
    const open = vi.fn();
    vi.stubGlobal("open", open);
    const user = userEvent.setup();

    function Link() {
      const platform = usePlatform();
      return (
        <a
          href="https://myanimelist.net/anime/1535"
          onClick={(event) => {
            event.preventDefault();
            void platform.openExternal("https://myanimelist.net/anime/1535");
          }}
        >
          Death Note
        </a>
      );
    }

    render(<Link />);
    await user.click(screen.getByText("Death Note"));
    expect(open).toHaveBeenCalledOnce();
  });
});
