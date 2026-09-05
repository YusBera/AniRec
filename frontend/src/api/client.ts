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

import type { ApiError, Feed, FeedbackResponse, OperationSnapshot, SystemState } from "./types";
import type { BackendConnection } from "../platform";

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
  health: () => request<{ status: string; version: string }>("/api/health"),

  systemState: () => request<SystemState>("/api/system/state"),

  feed: (includeHidden = false) =>
    request<Feed>(`/api/discover/feed?include_hidden=${includeHidden ? "true" : "false"}`),

  feedback: (payload: {
    profile_id: string;
    mal_id: number;
    action: "hidden" | "watch_later" | "sentiment";
    value?: boolean;
    sentiment?: "liked" | "disliked" | null;
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
