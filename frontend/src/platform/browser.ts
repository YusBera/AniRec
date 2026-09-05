/**
 * The web build. Same-origin API, ordinary links.
 *
 * There is no token here and that is correct rather than a gap: in the
 * browser the API is reached through the dev server's proxy (development) or
 * served from the same origin as the page (deployment), so the request is
 * same-origin and the per-launch token that protects the desktop's private
 * loopback service has nothing to protect against. See AniRec/api/security.py
 * for why that token exists only where a local service does.
 */

import type { BackendConnection, Platform } from "./types";

export const browserPlatform: Platform = {
  name: "browser",

  async connect(): Promise<BackendConnection> {
    return { baseUrl: "", token: null };
  },

  async openExternal(url: string): Promise<void> {
    // noopener/noreferrer: the opened page must not get a handle back to
    // this window, and MyAnimeList has no business reading the referrer of
    // a click inside a recommendation feed.
    window.open(url, "_blank", "noopener,noreferrer");
  },
};
