# Next-tab concept review — 2026-09-06

Status: the user selected concept C, **Library-led workspace**, through the local
selection page. No frontend tab code changed in this round. The selected image
is an approved compositional reference with the factual/poster corrections below.

## Authority and process

Fresh isolated PySide captures on the secondary monitor are stored beside this file. PRODUCT.md and DESIGN.md record the preservation boundary. Impeccable surface seed e94eea46 selected the prewritten structures 4, 2, 5: comparison matrix, split workbench, library-led workspace. UI/UX Pro Max targeted checks covered predictable navigation/back behavior, URL-addressable state, semantic navigation and preserved selection. Generated mockups use the actual captures as references, not a replacement theme.

## Review artifacts

- `.impeccable/mocks/decision/matrix.png`: aligned evidence and score rows.
- `.impeccable/mocks/decision/workbench.png`: browse list with persistent detail pane.
- `.impeccable/mocks/decision/library.png`: title-led shelves and paired score panels.
- Every image has an exact-prompt JSON sidecar and embedded prompt. Only
  `library.json` is marked approved.
- Local selection page: http://127.0.0.1:56766/ (session key fdd64048).

## Mockup limitations — do not literalize

These are AI-generated composition studies, not screenshots of implemented React tabs. Generated text includes errors and illustrative data. Source data and accessible semantic controls outrank image pixels:

- Latest explicit user correction: anime images are 2:3 portrait posters, not squares, including compact thumbnails. Existing Discover uses 152 × 228 logical pixels. Reopening concept A to resolve a Windows path error was not concept approval.

- 412 is the sample friend's total anime count, never a match score. Compatibility is 78%; shared anime 96; both rated 74. Remove duplicate shared-count fields.
- Personal match is a percentage, never a /10 rating. Actual sample pairs: Monster 94.6% / MAL 8.87; Death Note 92.4% / MAL 8.62; Steins;Gate 90.8% / MAL 9.07. Some mockups generated different numbers; discard those.
- Added dates, saved counts, hidden counts and extra metadata in the mockups are illustrative, not evidence from a user account. Do not implement unsupported dates. Fresh PySide Library is empty; the three saved rows are a proposed populated-state layout.
- Profile evidence shows selected disagreements, not necessarily the globally strongest. Avoid claiming the two examples explain the complete rating-bias calculation.
- Keep the existing icon family, persistent global navigation and status semantics; the workbench board omits repeated rails in two quadrants for space. Do not remove global navigation from actual pages.
- Sample mode is not a failed connection. Do not blindly carry the generated OFFLINE indicator into the React system status.
- Browser settings must reflect capabilities actually exposed by the web adapter, not imply native folder controls already work in React. Profile/Compare/Library/Settings API reads are not yet exposed.
- Destructive local-data actions require exact scope, confirmation, and backend support; mockup buttons authorize no deletion.

## Approval boundary

The A/B/C approval boundary is closed: C was selected. Next implementation must
derive per-tab desktop/mobile layouts from the Library-led structure, preserve
Discover and Qt, verify source values, and test real interactions and keyboard
navigation. The user's later 2:3-poster correction is part of the approval.
