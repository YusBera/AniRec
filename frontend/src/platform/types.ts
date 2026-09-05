/**
 * What the app needs from whatever it is running inside.
 *
 * The rule this interface exists to enforce: no React component imports
 * anything from `@tauri-apps/*`, and no component branches on which platform
 * it is running in. A component asks the platform to open a link or tell it
 * where the API is; whether that is `window.open` or a Tauri command is
 * settled once, here, at startup.
 *
 * Keeping this surface small is deliberate. Every method added is a thing
 * the browser build has to have an honest answer for - and "throw, because
 * we are in a browser" is rarely an honest answer for a product that is
 * supposed to ship on the web too. Domain calls do not belong here: they go
 * over HTTP to the Python API on both platforms, which is what keeps the two
 * clients architecturally identical.
 */

/** Where the API is, and what it will accept as proof of who is asking. */
export interface BackendConnection {
  /** Base URL with no trailing slash. Empty string means same-origin. */
  baseUrl: string;
  /** Per-launch token, or null when none is required (browser development). */
  token: string | null;
}

export type PlatformName = "browser" | "tauri";

export interface Platform {
  readonly name: PlatformName;

  /**
   * Resolve where the backend is. On the desktop this waits for the shell to
   * report that the Python process finished starting, so a caller that
   * awaits this never races the sidecar.
   */
  connect(): Promise<BackendConnection>;

  /**
   * Open a URL outside the application.
   *
   * In a browser this is a new tab. In the desktop shell it must reach the
   * user's real browser rather than navigating the webview - a MyAnimeList
   * page loaded inside the app window would be a dead end with no chrome to
   * escape from, and the MAL OAuth flow specifically depends on landing in a
   * browser the user is already signed into.
   */
  openExternal(url: string): Promise<void>;
}

/** Raised when the desktop shell cannot start or reach its backend. */
export class BackendUnavailableError extends Error {
  readonly reason: string;

  constructor(reason: string, message: string) {
    super(message);
    this.name = "BackendUnavailableError";
    this.reason = reason;
  }
}
