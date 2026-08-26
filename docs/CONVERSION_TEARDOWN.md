# AniRec conversion teardown — 1.3.0

Written 2026-08-26. Audit of the path from *stranger* to *first recommendation*, plus the
redesign that came out of it.

## The framing

AniRec has no free trial, because AniRec has no signup, no billing, and no hosted product.
It is a GPL desktop application. So the metric that matters is **activation**:

> stranger lands on the repo -> gets the app open -> sees a recommendation with its breakdown

Every finding below is judged against that sentence. The estimates are design judgment, not
measured data — there is no analytics anywhere in the funnel, which is leak zero.

## The five leaks

### 1. There is no download link. Anywhere.

No `.github/` directory, no release workflow, no tagged release, no attached binary. The
README references `dist\AniRec\AniRec.exe` (line 93) — a path that only exists *after the
visitor has cloned the repo, made a venv, installed PyInstaller, and run the build script*.
The only GitHub URL in the entire README is an attribution link to the owner's profile
(line 233).

A Windows desktop app shipped as a build script converts approximately nobody who is not
already a Python developer. This is not a UX problem, it is the whole funnel.

**Fix:** tag `v1.3.0`, attach the `onedir` zip, put a download button in the first five lines
of the README.

### 2. The free trial already exists, and it is buried

`WIZARD_TEXT.welcome_demo` — *"Look around with sample data"*, no account, nothing saved — is
exactly the right product instinct. It is the trial. Then:

- it renders as `buttonRole="secondary"` (`AniRec/gui/setup_wizard.py:132`), which the
  stylesheet paints as a flat surface-coloured button (`AniRec/gui/qss_builder.py:91`);
- it sits *below* a hint whose second clause is "takes about two minutes"
  (`WIZARD_TEXT.welcome_connect_hint`);
- the wizard footer's primary button marches the visitor into the API wall instead.

The zero-friction path is styled like the cancel button.

**Fix:** invert the welcome page. Sample data becomes the primary action. Connecting a
MyAnimeList account becomes the quiet second option, offered *after* the visitor has seen a
feed and wants it to be about them.

### 3. The wall

`docs/images/anirec-first-run-wizard.png` is the first thing a new user sees. It asks for a
**Client ID**, a **Client Secret**, and a **Redirect URI**, behind four numbered instructions,
with a disabled *Validate and Continue* at the bottom — before a single anime has been shown.

The wizard copy is genuinely good; someone thought hard about explaining what a Client Secret
is and why it is safe. That effort is spent in the wrong place. No amount of reassurance makes
OAuth application registration a reasonable price for *not knowing yet whether the app is any
good*.

**Fix:** the wall stays, but it moves. Nobody should reach it before they have seen the
product work.

### 4. The differentiator is broken in the marketing screenshot

The pitch is "recommendations you can actually interrogate — every score comes with a
breakdown that adds up to it." In `docs/images/anirec-s15-modern-for-you.png`, five cards in a
row read:

> No recommendation explanation is available.

That is the entire wedge, absent, in the image chosen to represent the product. Alongside it,
five identical grey "A" placeholders where cover art should be. Anime is a visual medium; the
grid has had the one thing removed that makes it want to be looked at.

**Fix:** never ship a card that announces the product's promise is unavailable — fall back to
the genre contributions, which are always available. Re-shoot the screenshots with covers
resolved.

### 5. Thirty tap targets on one screen

Every card carries Like / Not for me / View Details / Watch Later / Open on MyAnimeList /
Hide. Six actions, five cards, thirty targets, no visual hierarchy between them. Plus
`Personal match: 89.4%` — one decimal of false precision on a taste model built from a
double-digit number of ratings.

**Fix:** two actions per card (Like / Not for me), everything else behind hover or the detail
view. Round the match to whole numbers.

## Ranked plan

| # | Fix | Effort | Why it ranks here |
|---|-----|--------|-------------------|
| 1 | Tag a release, attach the build, download button in the README's first screen | hours | Without it nothing else matters |
| 2 | Ship the landing page (`docs/landing/index.html`) and point the repo at it | done — needs a release URL | Gives the download somewhere to land |
| 3 | Invert the wizard welcome: sample data primary, OAuth secondary | ~1 hour | Un-buries the trial |
| 4 | Rewrite the README top-fold: screenshot, one sentence, download. Spec sheet moves below | ~1 hour | Currently opens with a version number and thirteen bullets |
| 5 | Explanation fallback on cards; never render "no explanation available" | half day | Protects the wedge |
| 6 | Two actions per card; whole-number match | half day | Decision paralysis, false precision |

Items 1-4 are most of the available upside and are about a day of work combined.

## The landing page

`docs/landing/index.html` — self-contained, no build step, no external assets beyond Google
Fonts.

### Design direction: the scoring bench

The product's real differentiator is that the score is *assembled from parts that sum*. So the
page is built as a piece of rack-mounted audio equipment: genre contributions are channel
faders, the match percentage is the master readout, and the hero's job is to show the number
being built rather than asserting it in a headline.

This is not decoration. The layout device encodes the one true thing about the product that
competitors cannot claim.

### Tokens

| Role | Dark (default) | Light |
|------|----------------|-------|
| Ground | `#0B1410` lacquer green-black | `#E3E7DD` sage paper |
| Panel | `#132019` | `#EFF1E9` |
| Text | `#E9E5D6` bone silkscreen | `#16241F` lacquer ink |
| Structural accent | `#C6A15B` oxidized brass | `#8A6A22` bronze |
| Signal / live values | `#6FC6C0` aqua | `#2C7C74` deep teal |

Two accents, warm and cool, on a green-biased neutral — deliberately not the near-black-plus-
one-neon-pop that generated pages default to. The light theme is the silkscreen artwork the
panel was printed from, not an inversion.

**Type:** Big Shoulders Display for headlines (condensed, industrial, reads as equipment
legend), Zen Kaku Gothic New for body (Japanese gothic, grounds it culturally), Azeret Mono
for every number (chunky, tabular).

### Interaction

- One orchestrated page load: the master readout counts up while the contribution bars stagger
  in beneath it, so the first thing a visitor sees is the score being *derived*.
- The hero demo is CSS-only — three radio inputs switch the selected title and re-animate the
  breakdown. No JavaScript required for the core proof.
- `prefers-reduced-motion` drops every reveal to a static end state.

### Before this ships

The download CTA points at `https://github.com/YusBera/AniRec/releases`, **which 404s until a
release is tagged.** Fix #1 in the table above is a prerequisite, not a nice-to-have. The
secondary CTA — "look around with sample data" — is honest today and is the one doing the
conversion work.

### Where it lives

- Source: `docs/landing/index.html` — one file, no build step, no bundler.
- Published preview: https://claude.ai/code/artifact/d3bc1a71-dbad-4416-ad6b-c8888a4bc9c0
- To host it from this repo, enable GitHub Pages on `main` with `/docs` as the source; the
  page is already at the `landing/` path and needs no configuration.

The file opens with `<title>` and the font `<link>` rather than a `<!doctype>` wrapper, which
parses correctly in every browser and lets the same file be published as-is.

### Accessibility notes

- The muted tone was darkened in light mode and lightened in dark mode after a contrast check;
  the original pair failed AA against both grounds at legend sizes.
- The breakdown demo is four radio inputs and four labels, so it is keyboard-operable with
  arrow keys and has a visible focus ring on the active tab.
- `prefers-reduced-motion` collapses every reveal, the count-up, and smooth scrolling.

---

# Part two: the desktop UI

The landing page sells the app. This part is the app itself. Frontend only —
`AniRec/gui/` and its resources. No service, scoring, or infrastructure code was
touched.

## What was actually wrong

The token system was not the problem. `design_tokens.py` already had colour
roles, a relative type scale, generated stylesheets, and a parity test proving
light and dark style the same selectors. Whoever built that knew what they were
doing. The problem was the *choices* made inside it, and the information design
on top of it.

Measured on the app itself at 1280x720, in sample mode:

| Symptom | Measurement |
|---|---|
| Chrome above the feed | the first card began ~365px down a 720px window |
| Accent-filled blocks on one screen | five: nav item, connect, refresh, top-up, and every match bar |
| Off-palette controls | the Adventurousness slider drew in the Windows system blue |
| Group titles | the card border ran through the middle of the words |
| Body font stack | `"Segoe UI", "Inter", ...` |

## The palette

Retired the terracotta-on-near-black. That combination is the single most
common look a generated interface lands on, and using one accent for
everything meant nothing on screen could be more important than anything else.

| Role | Dark | Light | Means |
|---|---|---|---|
| Ground | `#0A120E` lacquer green-black | `#E9ECE4` sage paper | — |
| Text | `#E9E5D6` bone | `#16241F` lacquer ink | — |
| Accent | `#C6A15B` brass | `#7A5D1C` bronze | *yours*: your match, your taste, the one action |
| Signal | `#6FC6C0` aqua | `#2C7C74` teal | *the system*: focus, selection, saved |

Two accents that mean different things, on a neutral biased slightly toward the
panel. OLED and the user's custom gradient derive from these, so all four themes
moved together and the parity test still passes: 211 selectors in every theme.

## Typography

One family became three, all shipping with Windows 10 and 11, so there is
nothing to bundle:

- **body** — Segoe UI Variable Text. `Inter` removed from the stack.
- **display** — Bahnschrift, Microsoft's DIN. Headings, page titles, group
  labels. Technical and slightly condensed, so a heading reads as a heading
  rather than as bold body copy.
- **mono** — Cascadia Mono. Every number that belongs in a column: match
  scores, MAL ratings, metric values.

## Structure

- **One status strip instead of two banners.** The profile pill, the connection
  pill and the full-width sample-data banner were three stacked rows carrying
  three facts. They are one line now, and the feed starts at y=287 instead of
  ~365 — about 11% of the window height returned to content, on every page.
- **Navigation stopped shouting.** The selected page was a solid accent slab.
  It is a 3px rail and a text colour. The rail exists but is transparent on
  every item, so nothing shifts when the selection moves.
- **One primary action per screen.** "Recommend 5 more" dropped to secondary;
  it is a top-up beside a summary line, not the reason you opened the page.
- **Three frames deep became one.** The feed header was a bordered, rounded
  card containing a bordered summary box and a bordered control box. Tone
  separates them now; only actual cards keep an outline.
- **Radii tightened** from 6/10/14/20 to 4/6/9/13, so a control and a card are
  no longer the same kind of object.

## The activation fix

`WelcomePage` led with a pitch for registering a MyAnimeList API application
and put "Look around with sample data" underneath it as a *secondary* button.
The cheapest path through the product was styled like the way out of it.

Sample data is now the primary, full-width action, with "No account needed.
Nothing is saved." under it, and connecting is the quiet alternative reached
through Next.

## Defects found and fixed along the way

1. **Disabled buttons did not look disabled.** Qt follows CSS2 specificity,
   where `:disabled` and `[buttonRole="primary"]` score identically, so the one
   written last won. `:disabled` was written first. A disabled primary button
   rendered as a fully enabled accent block — "Recommend 5 more" has been
   showing as pressable while disabled. The disabled rules now come last.
2. **The card grid miscounted columns at any GUI scale above 100%.** Cards lay
   out at `scaled(CARD_WIDTH)` but the stride was measured with the unscaled
   constant. At 125% that asked for 1168px of cards in a 1006px viewport; at
   150%, 1392px. Both are options in Settings. `scaling.py` states the rule in
   its own docstring: hand-chosen pixel sizes go through `scaled()`.
3. **The slider was never styled**, so Windows drew it in the system highlight
   colour.
4. **Group box titles collided with their own border.** The title sat on the
   margin; it sits inside the padding box now, as a section label.
5. **Both placeholder SVGs were painted in the retired palette** and were the
   loudest thing on a card. Recoloured and deliberately dimmed — a missing
   cover should read as absence.

## Deliberately not done

- **A checkmark glyph for checked checkboxes.** Qt stops drawing its own
  indicator once the sub-control is restyled, so a real tick means shipping a
  light and a dark icon and threading a resolved filesystem path into a
  stylesheet that is currently a pure function of the tokens. Not worth that
  coupling for one glyph. The filled brass indicator reads as on/off.
- **Spin box stepper styling.** Attempted, reverted: styling the sub-control
  suppressed Qt's chevrons and left two blank blocks. The platform steppers
  are plain, but they are steppers.
- **Shrinking the card.** A card is 620px. At 1440x900 and 1920x1080 the whole
  card is visible; only at the 1280x720 minimum is it clipped, at 70%. Cutting
  the cover art to fix the smallest window would cost the majority case the
  thing that makes an anime grid worth looking at. Left alone deliberately.
- **Collapsing the six per-card actions into two plus an overflow.** Still the
  right call for decision load, but the tests drive `details_button`,
  `watch_later_button`, `mal_button` and `hide_button` directly and
  `test_card_grid_geometry` asserts on their positions. It needs the tests
  reworked with it, which is a larger change than a repaint.
