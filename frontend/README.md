# AniRec frontend

React + TypeScript. **One page — Discover — and it is a validated proof of
concept, not the product.** The shipping application is the PySide6 desktop app
in `AniRec/gui/`, which is untouched and still the reference implementation.

Read [../docs/design/MIGRATION_HANDOFF.md](../docs/design/MIGRATION_HANDOFF.md)
before changing anything here.

## Run it

Two processes. The API first:

```powershell
.\.venv\Scripts\python.exe -m AniRec.api
```

It serves `http://127.0.0.1:8770` and prints a readiness line. Then:

```powershell
npm install
npm run dev
```

Vite serves `http://localhost:5173` and proxies `/api` to the backend, so the
browser only ever talks to one origin.

With no MyAnimeList profile configured the feed falls back to the bundled
sample library and marks itself `source: "sample"`, so this runs without
credentials.

## Scripts

| Command | What |
|---|---|
| `npm run dev` | Vite dev server with the API proxy |
| `npm test` | Vitest |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm run generate:api-types` | Regenerate `src/api/generated/schema.d.ts` from FastAPI |
| `npm run verify:api-types` | Fail if those types are stale — use in CI |
| `npm run ci` | verify types, typecheck, test |

## Types are generated

`AniRec/api/models.py` is the source of truth. `src/api/generated/schema.d.ts`
is produced from FastAPI's OpenAPI document and **must not be edited by hand**;
`src/api/types.ts` holds only aliases into it, plus the server-sent-event frame
types, which are hand-written because OpenAPI cannot describe the shape of
individual SSE frames.

Change a Pydantic model, run `npm run generate:api-types`, and every stale
usage becomes a type error rather than a runtime `undefined`.

## What is not here yet

**There is no Tauri application.** `src/platform/tauri.ts` is written against a
Rust shell that does not exist in this repository: it calls
`invoke("backend_connection")` and imports `@tauri-apps/plugin-opener`, and
neither has a counterpart yet. `isTauri()` is false in every environment that
exists today, so that file is never loaded — the bundle splits it into its own
lazy chunk, which is how the browser build stays clean.

`AniRec-api.spec` at the repository root builds the Python API as a standalone
binary (85 MB, no Qt, verified serving the real feed). Nothing spawns it yet.
It exists so the payload could be measured before committing to a desktop
shell.

Both are groundwork for a Tauri validation stage that has not run. Do not treat
either as working desktop support.

## Structure

```text
src/
  api/         HTTP client, hooks, generated types
  discover/    the one page, its components and CSS
  platform/    browser vs desktop seam - the only place Tauri may be imported
  styles/      tokens.css (generated), base, instrument design system
```

The rule that keeps the web build shippable: **no component imports
`@tauri-apps/*` or branches on which platform it is running in.** It asks
`usePlatform()` for a capability. `src/platform/` is the only exception, and
its Tauri implementation is dynamically imported so a browser never resolves
the dependency.

No stylesheet here contains a hex value. Colours come from
`styles/tokens.css`, generated from `AniRec/gui/design_tokens.py` by
`scripts/build_theme.py` — the same file the Qt stylesheets are built from, so
the two frontends cannot drift apart.
