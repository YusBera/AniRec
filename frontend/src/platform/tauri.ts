/**
 * The desktop build. The Rust shell owns the backend; this asks it where.
 *
 * >>> THE RUST SIDE DOES NOT EXIST YET. <<<
 *
 * There is no `src-tauri/` in this repository. The `backend_connection`
 * command invoked below is unimplemented, and no Tauri application has been
 * built or run. `isTauri()` is false in every environment that exists today,
 * so this module is never loaded - the production bundle splits it into its
 * own lazy chunk precisely so the browser build never resolves it.
 *
 * This file is groundwork for a Tauri validation stage that has not run, kept
 * here so the seam it defines could be designed and tested against a fake.
 * Do not read it as evidence that desktop packaging works. See
 * docs/design/MIGRATION_HANDOFF.md, "Proven, and not".
 *
 * The two Tauri entry points in the entire frontend are here:
 *
 *   invoke("backend_connection")  -> { baseUrl, token }
 *   openUrl(url)                  -> the user's real browser
 *
 * Everything else the desktop app does travels the same HTTP path the web
 * build uses. That is the property worth protecting: if this file grew a
 * third domain-shaped command, the two clients would start to diverge and
 * the browser build would quietly become the lesser one.
 *
 * The imports are dynamic so that this module can be *referenced* in a
 * browser bundle without the Tauri packages having to resolve at load time.
 * `detect()` decides which platform is live before either is imported.
 */

import { BackendUnavailableError, type BackendConnection, type Platform } from "./types";

/** Mirrors the Rust `BackendConnection` returned by the `backend_connection` command. */
interface RawConnection {
  base_url: string;
  token: string;
  error?: string;
  message?: string;
}

export const tauriPlatform: Platform = {
  name: "tauri",

  async connect(): Promise<BackendConnection> {
    const { invoke } = await import("@tauri-apps/api/core");
    try {
      // The Rust side does not answer until the Python child has printed its
      // readiness line, so awaiting this is the whole of the frontend's
      // startup synchronisation - there is no polling loop here.
      const raw = await invoke<RawConnection>("backend_connection");
      return { baseUrl: raw.base_url.replace(/\/$/, ""), token: raw.token };
    } catch (caught) {
      // Rust returns a structured failure for every path where the backend
      // could not be started; anything else is genuinely unexpected.
      const detail = caught as RawConnection | string;
      const reason = typeof detail === "string" ? "unknown" : (detail.error ?? "unknown");
      const message =
        typeof detail === "string" ? detail : (detail.message ?? "The AniRec service did not start.");
      throw new BackendUnavailableError(reason, message);
    }
  },

  async openExternal(url: string): Promise<void> {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  },
};
