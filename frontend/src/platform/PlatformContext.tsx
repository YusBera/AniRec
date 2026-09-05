/**
 * Resolve the platform once, configure the API client, then render.
 *
 * This is the only place startup ordering lives. Components never wait for
 * the backend themselves - by the time one renders, `configureApi` has
 * already been told where the API is, so `api.feed()` works identically in a
 * browser tab and inside the desktop shell.
 *
 * The desktop's `connect()` does not resolve until the Rust shell reports
 * that the Python child finished starting, which is why the failure state
 * here is a real, designed screen rather than a spinner that never stops:
 * a backend that cannot start is the one startup failure a packaged desktop
 * application is most likely to actually show a user.
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { configureApi } from "../api/client";
import { browserPlatform } from "./browser";
import { getPlatform } from "./index";
import { BackendUnavailableError, type Platform } from "./types";

// Defaults to the browser rather than to null, so a component rendered
// outside the provider - which is every component under test - still gets a
// working platform instead of a thrown error. The browser is the honest
// default: it is what the code does when nothing has told it otherwise.
const PlatformContext = createContext<Platform>(browserPlatform);

export function usePlatform(): Platform {
  return useContext(PlatformContext);
}

type Status =
  | { phase: "connecting" }
  | { phase: "ready"; platform: Platform }
  | { phase: "failed"; message: string; reason: string };

export function PlatformProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>({ phase: "connecting" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const platform = await getPlatform();
        const connection = await platform.connect();
        if (cancelled) return;
        configureApi(connection);
        setStatus({ phase: "ready", platform });
      } catch (caught) {
        if (cancelled) return;
        const failure =
          caught instanceof BackendUnavailableError
            ? { message: caught.message, reason: caught.reason }
            : {
                message: "AniRec could not start its local service.",
                reason: "unknown",
              };
        setStatus({ phase: "failed", ...failure });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status.phase === "connecting") {
    return (
      <div className="state-panel" role="status">
        <span className="led amber live" />
        <h2>Starting AniRec</h2>
        <p className="lbl">Waiting for the local service</p>
      </div>
    );
  }

  if (status.phase === "failed") {
    return (
      <div className="state-panel" data-tone="error" role="alert">
        <span className="led off" />
        <h2>AniRec could not start its local service</h2>
        <p>{status.message}</p>
        <p className="lbl">Reason: {status.reason}</p>
        <button type="button" className="btn" onClick={() => window.location.reload()}>
          Try again
        </button>
      </div>
    );
  }

  return (
    <PlatformContext.Provider value={status.platform}>{children}</PlatformContext.Provider>
  );
}
