/**
 * Pick a platform once, at startup, and hand the same object to everything.
 *
 * Detection is a property check rather than a build-time flag, because the
 * same bundle is served both ways during development: `npm run dev` in a
 * browser and `npm run tauri:dev` in the shell load identical JavaScript
 * from the same Vite server. A compile-time constant would have to be right
 * before anyone knows which one is about to run it.
 */

import { browserPlatform } from "./browser";
import type { Platform } from "./types";

export type { BackendConnection, Platform, PlatformName } from "./types";
export { BackendUnavailableError } from "./types";

declare global {
  interface Window {
    /** Injected by the Tauri webview. Absent in every browser. */
    __TAURI_INTERNALS__?: unknown;
  }
}

export function isTauri(): boolean {
  return typeof window !== "undefined" && window.__TAURI_INTERNALS__ !== undefined;
}

let cached: Promise<Platform> | null = null;

/**
 * The platform this app is running on.
 *
 * Async because the Tauri implementation is imported dynamically - a browser
 * bundle must never have to resolve `@tauri-apps/*` at module load, or the
 * web build would carry (and fail on) desktop-only dependencies.
 */
export function getPlatform(): Promise<Platform> {
  if (cached === null) {
    cached = isTauri()
      ? import("./tauri").then((module) => module.tauriPlatform)
      : Promise.resolve(browserPlatform);
  }
  return cached;
}

/** Test seam. Resets the memoised choice so a suite can swap platforms. */
export function __resetPlatformForTests(next?: Platform): void {
  cached = next ? Promise.resolve(next) : null;
}
