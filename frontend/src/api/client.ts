/**
 * The HTTP boundary, in one file.
 *
 * Every failure becomes an ApiError - the same redacted, traceback-free model
 * presentable_error already produces for the desktop dialog - so a component
 * never has to decide what a network failure means or risk rendering a
 * traceback. A transport failure is given the same shape locally rather than a
 * different one, because "offline" and "the server said no" reach a card as
 * the same kind of thing: something to show a retry for.
 *
 * The client is configured once at startup with wherever the backend turned
 * out to be. In a browser that is the current origin and no token; in the
 * desktop shell it is a loopback port the Rust side chose and the per-launch
 * token it generated. Components never see the difference - they call
 * `api.feed()` either way.
 */

import type { AccountImports, AccountResult, PreferencesWrite, ActivityEvent, ActivityStatus, ActivityReceipt, ApiError, Feed, FeedbackResponse, MalImport, OperationList, OperationSnapshot, SystemState } from "./types";
import type { BackendConnection } from "../platform";
import type { ProfileRead, CompareRead, SettingsRead, SettingsWrite, LibraryRead, RecommendationViewModel } from "./types";

export class AniRecApiError extends Error {
  readonly detail: ApiError;
  readonly status: number;

  constructor(detail: ApiError, status: number) {
    super(detail.title);
    this.name = "AniRecApiError";
    this.detail = detail;
    this.status = status;
  }
}

const OFFLINE: ApiError = {
  code: "network_error",
  title: "AniRec could not reach its local service",
  description: "The request did not complete.",
  solution: "Confirm the AniRec service is running, then try again.",
  retryable: true,
};

// Same-origin and unauthenticated until told otherwise, which is exactly the
// browser case - so a web build that never calls configure() still works.
let connection: BackendConnection = { baseUrl: "", token: null };

export function configureApi(next: BackendConnection): void {
  connection = { baseUrl: next.baseUrl.replace(/\/$/, ""), token: next.token };
}

export function apiUrl(path: string): string {
  return `${connection.baseUrl}${path}`;
}

function headers(extra?: HeadersInit): HeadersInit {
  const base: Record<string, string> = { "Content-Type": "application/json" };
  if (connection.token) {
    base["X-AniRec-Token"] = connection.token;
  }
  return { ...base, ...(extra as Record<string, string> | undefined) };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...init, headers: headers(init?.headers) });
  } catch {
    throw new AniRecApiError(OFFLINE, 0);
  }
  if (!response.ok) {
    let detail: ApiError = { ...OFFLINE, title: `Request failed (${response.status})` };
    try {
      const body = await response.json();
      if (body?.error) {
        detail = body.error as ApiError;
      } else if (typeof body?.detail === "string") {
        detail = { ...detail, description: body.detail, solution: "" };
      }
    } catch {
      /* A body that is not JSON tells us nothing more than the status did. */
    }
    throw new AniRecApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export const api = {
  profile: (sample = false) => request<ProfileRead>(`/api/workspace/profile?sample=${sample}`),
  compare: (sample = false, username = "") => request<CompareRead>(`/api/workspace/compare?sample=${sample}&username=${encodeURIComponent(username)}`),
  settings: () => request<SettingsRead>("/api/workspace/settings"),
  saveSettings: (payload: SettingsWrite) => request<SettingsRead>("/api/workspace/settings", { method: "POST", body: JSON.stringify(payload) }),
  library: (profileId: string) => request<LibraryRead>(`/api/workspace/library?profile_id=${encodeURIComponent(profileId)}`),
  resolveTitle: (profileId: string, malId: number) => request<RecommendationViewModel>("/api/workspace/library/resolve", { method: "POST", body: JSON.stringify({ profile_id: profileId, mal_id: malId }) }),
  activityStatus: () => request<ActivityStatus>("/api/discover/activity"),
  activitySetting: (enabled: boolean) => request<{ enabled: boolean }>("/api/discover/activity/settings", { method: "POST", body: JSON.stringify({ enabled }) }),
  clearActivity: () => request<{ enabled: boolean }>("/api/discover/activity", { method: "DELETE" }),
  activityEvent: (event: ActivityEvent) => request<ActivityReceipt>("/api/discover/activity", { method: "POST", body: JSON.stringify(event) }),

  health: () => request<{ status: string; version: string }>("/api/health"),

  systemState: () => request<SystemState>("/api/system/state"),

  /** First-time setup: start with a public MyAnimeList list (D-020). */
  importMalProfile: (username: string) => request<MalImport>("/api/onboarding/mal-profile", { method: "POST", body: JSON.stringify({ username }) }),

  // Accounts (D-021). The session is an HttpOnly cookie the browser keeps;
  // no token is ever handled here.
  account: () => request<AccountResult>("/api/account"),
  register: (email: string, password: string) => request<AccountResult>("/api/account/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  signIn: (email: string, password: string) => request<AccountResult>("/api/account/sign-in", { method: "POST", body: JSON.stringify({ email, password }) }),
  signOut: () => request<AccountResult>("/api/account/sign-out", { method: "POST" }),
  imports: () => request<AccountImports>("/api/account/imports"),
  changePassword: (currentPassword: string, newPassword: string) => request<AccountResult>("/api/account/password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }),
  deleteAccount: (password: string | null) => request<AccountResult>("/api/account/delete", { method: "POST", body: JSON.stringify({ password }) }),
  /** A same-origin download: the browser sends the session cookie itself. */
  exportUrl: () => apiUrl("/api/account/export"),
  savePreferences: (values: PreferencesWrite) => request<SettingsRead>("/api/workspace/preferences", { method: "POST", body: JSON.stringify(values) }),
  chooseImport: (profileId: string) => request<AccountImports>("/api/account/imports/active", { method: "POST", body: JSON.stringify({ profile_id: profileId }) }),

  operations: () => request<OperationList>("/api/operations"),
  operation: (id: string) => request<OperationSnapshot>(`/api/operations/${encodeURIComponent(id)}`),

  feed: (includeHidden = false) =>
    request<Feed>(`/api/discover/feed?include_hidden=${includeHidden ? "true" : "false"}`),

  feedback: (payload: {
    profile_id: string;
    mal_id: number;
    action: "hidden" | "watch_later" | "sentiment";
    value?: boolean;
    sentiment?: "liked" | "disliked" | null;
    feed_id?: string | null;
    genres?: string[];
    title?: string;
  }) =>
    request<FeedbackResponse>("/api/discover/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  startOperation: (kind: string, payload: Record<string, unknown> = {}) =>
    request<OperationSnapshot>(`/api/operations/${kind}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  cancelOperation: (id: string) =>
    request<{ cancelled: boolean }>(`/api/operations/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),

  /**
   * The SSE URL for one operation.
   *
   * EventSource cannot send headers, so a token-protected desktop backend
   * takes it as a query parameter here rather than as X-AniRec-Token. That is
   * an acceptable narrowing on loopback - the URL never leaves the machine,
   * there is no proxy or CDN to log it, and the alternative (a fetch-based
   * SSE reader written by hand) is a lot of machinery to avoid it. It is
   * called out because it is the one place the token travels in a URL.
   */
  eventsUrl: (id: string) => {
    const base = apiUrl(`/api/operations/${encodeURIComponent(id)}/events`);
    return connection.token
      ? `${base}?token=${encodeURIComponent(connection.token)}`
      : base;
  },
};
