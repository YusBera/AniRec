# Workspace functional extension

Updated 2026-09-07 for the review branch. Start with [LATEST_AGENT_HANDOFF.md](LATEST_AGENT_HANDOFF.md) for current transfer instructions and verification limits. No deployment.

## Scope now implemented

- Library reads saved title metadata from the full result and completed/top/candidate CSV snapshots, beyond the visible feed. Missing saved IDs can explicitly request MAL details. Metadata-only titles display N/A personal match; existing scores are not invented. Sample decisions remain in memory. Network-resolved details currently last for the mounted page session.
- Profile adds the existing provider's archetype, highly ranked low-rated evidence, hidden gems, rating histogram, genre/studio title disclosures, eras/seasons, watching habits and timeline. Unsupplied statistics remain unavailable; no history is inferred from air dates.
- Compare joins the active local completed snapshot with a public user's completed list. It carries both scores, absolute differences and source counts, with separate unrated shared titles. No aggregate compatibility algorithm exists, so live compatibility is N/A. Sample compatibility remains explicitly labelled. NSFW preference affects titles returned. Invalid responses and foreign pagination are refused.
- Settings now saves allowlisted recommendation and desktop appearance preferences through SettingsService. Credentials and unexposed fields survive saves; unknown request fields, invalid ranges and batch size above candidate pool are refused. Unreadable settings cannot be overwritten with displayed defaults. Save errors retain edits; discard returns to last successful save. Browser theme remains unchanged by desktop appearance values.

New routes: GET /api/workspace/library, POST /api/workspace/library/resolve, POST /api/workspace/settings. Existing profile response adds the existing archetype. Existing compare route now supports live completed-list evidence. All share the existing API token boundary. API types remain generated from Python.

## Evidence

- Frontend CI: 56 tests, types and generated schema pass.
- Production build: pass. Main JS200.34kB/61.83gzip; CSS35.66kB/7.34gzip.
- Scoped Python: 56 tests pass across test_api_workspace, test_api_boundary, test_settings_and_tokens, test_taste_profile_service and test_mal_mapping.
- Full Python run completed after the desktop Profile cache repair: 738 passed, 2 failed, 740 total. Both credential-signature tests flag only ignored frontend/node_modules dependency files using the generic 32-hex pattern. No scanned file outside node_modules matched. See reports/workspace-full-tests-summary.md and the original XML; the tests were not changed to suppress failures.
- Two distinct user-authorized MAL accounts passed the API check: existing local NeoBalls_ snapshot (167) versus actual remote Kuroboshi_ completed list (555), with 108 shared, 89 both rated and 19 unrated shared. All 108 score pairs and supplied differences were verified. Compatibility remains null; no account writes. See reports/workspace-live-compare-check.json. This is API coverage, not populated live browser certification or a fresh local sync. The earlier same-account check is superseded by this additional evidence.
- Browser at1440x1000 and390x844: isolated settings save5to7 survives reload; missing Client ID gives an actionable message; Monster absent from test feed loads from CSV with N/A match; sample comparison remains explicit; Profile disclosures work with keyboard. Mobile poster80x120; document has no horizontal overflow.
- Captures and review packet: .impeccable/review/extension/. Some exports omit scrollbar area or scale pixels; see packet. Invalid library fullpage capture was replaced with a valid viewport capture. Fullpage Profile captures include all sections.
- Mechanical detector: [] once. Independent extension review completed: finish-review.md identified stale capability documentation; finish-verdict.md records its resolution and scoped ship disposition. That verdict does not certify the whole surface, populated live-result rendering, full-suite success or the separate desktop cache repair.

## Preserved boundaries

PySide visual styling, shared design tokens and recommendation/scoring algorithms are unchanged. A separate nonvisual Profile cache repair in main_window.py sets loaded-profile state after local loading and invalidates it for sample loading; all 10 dashboard tests passed afterward. Concept C remains the approved composition reference, all anime artwork2:3. Previous Impeccable finish records and raw failed pixel comparison are historical and remain intact. This extension is not deployment, Tauri packaging, browser account setup, or a new compatibility model.

Real account settings, credentials and profiles were only read. Browser writes used the ignored reports/ui-workspace-sample root and the explicitly named workspace_test_fixture. No account secrets are in the captures or test reports.
