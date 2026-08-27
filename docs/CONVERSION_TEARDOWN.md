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

### 1. The download sells a version visitors cannot get

The current landing artifact identifies the product as 1.3.0, but the public GitHub "Latest"
release is v1.2.2. The CTA points to the generic releases index rather than to a stable asset.
That makes the strongest marketing claim impossible to verify before download and delivers an
older experience after it. A version mismatch at the conversion boundary looks indistinguishable
from neglect or a bait-and-switch, even when the repository is legitimate.

**Fix:** tag and package the exact reviewed 1.3.0 build, link the Windows asset directly (or use
`/releases/latest`), publish its SHA-256, and keep the unsigned-build warning beside the CTA.

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

### 4. The artifact and the downloaded app spoke different design languages

The old documentation screenshots are not evidence of the current product, so they were not
used for this comparison. The current landing source and the running desktop app were inspected
directly. The landing made score explainability tactile: rack legends, scanlines, a large master
readout, a segmented contribution rail, calibration ticks, and parts that visibly add to a sum.
The old app detail view reduced the same differentiator to a small percentage and a newline list
below generic metadata and five equal-width action rectangles.

That is worse than visual inconsistency. It makes the landing look like a concept render for a
different product. Excitement becomes suspicion at exactly the moment trust should compound.

**Fix implemented:** the desktop detail view is now the Score Inspector described below. Current
screenshots still need to be recaptured with resolved cover art before the release is promoted.

### 5. Thirty tap targets on one screen

Before the hierarchy pass, every card carried Like / Not for me / View Details / Watch Later /
Open on MyAnimeList / Hide as button-shaped controls. Six actions, five cards, thirty rectangles.
It also showed `Personal match: 89.4%` — one decimal of false precision on a taste model built
from a double-digit number of ratings.

**Fix implemented:** Like and Not for me are the only full button pair. Details, MyAnimeList,
and Hide are quiet text actions; Later is the compact saved-state control; the card rounds the
match to a whole number. The Score Inspector retains the decimal because that surface exposes
the underlying arithmetic and is the one place the precision has meaning.

## Ranked plan

| # | Fix | Effort | Why it ranks here |
|---|-----|--------|-------------------|
| 1 | Ship the reviewed 1.3.0 asset and make every CTA resolve to that exact build | hours | The current landing promises a version the visitor cannot download |
| 2 | Ship the landing page (`docs/landing/index.html`) and point the repo at it | done — needs a release URL | Gives the download somewhere to land |
| 3 | Invert the wizard welcome: sample data primary, OAuth secondary | ~1 hour | Un-buries the trial |
| 4 | Rewrite the README top-fold: screenshot, one sentence, download. Spec sheet moves below | ~1 hour | Currently opens with a version number and thirteen bullets |
| 5 | Explanation fallback on cards; never render "no explanation available" | done | Protects the wedge |
| 6 | Give only the decision pair button weight; whole-number card match | done | Removes decision noise without burying the inspector |

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

The download CTA points at `https://github.com/YusBera/AniRec/releases`, while the public latest
release is older than the 1.3.0 experience the page demonstrates. Fix #1 in the table above is a
prerequisite, not a nice-to-have. The secondary CTA — "look around with sample data" — is honest
today and is the one doing the conversion work.

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
  it is a top-up beside a summary line, not the reason you opened the page. If
  no candidate pool exists, the dead action is absent instead of becoming a
  large disabled rectangle.
- **Three frames deep became one.** The feed header was a bordered, rounded
  card containing a bordered summary box and a bordered control box. Tone
  separates them now; only actual cards keep an outline.
- **Radii tightened** from 6/10/14/20 to 4/6/9/13, so a control and a card are
  no longer the same kind of object.
- **Library tabs stopped being buttons in a box.** The outer rounded rectangle
  and filled selection rectangles became a single baseline with an active
  brass underline, closer to an IDE tool surface than a generic settings card.
- **Empty means empty.** An empty collection keeps the Cards/List/Table choice
  for consistency and keyboard users, but dead Filters and Show hidden controls
  disappear until that collection actually contains something.

## Artifact parity: the Score Inspector

Anime details now carry the same scoring-bench language as the landing artifact:

- a rack legend and restrained 4px scanlines painted from resolved theme tokens;
- a large animated match readout and calibrated 0–100 rail;
- real contribution segments, colour-keyed rows, ticks, and an explicit raw
  sum-to-display relationship rather than a debug-text dump;
- a final-score marker that exposes a service-side calibration mismatch instead
  of stretching a contributor to make the graphic look correct;
- previous/next recommendation controls plus Left/Right keyboard navigation, so
  the inspector supports comparison rather than behaving like a dead-end modal;
- a collapsed synopsis and compact utility links, keeping the scoring proof in
  the first viewport.

The same `InstrumentPanel` texture is used on the Discover action strip and the
recommendation feedback band. The effect is intentionally restrained: enough
to make the product feel like one system, not enough to compromise body copy.

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
   showing as pressable while disabled. The disabled rules now come last, text
   actions stay transparent, and the unavailable top-up action is hidden.
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
- **Hiding secondary card actions in an overflow.** The card still exposes six
  semantic actions, but only Like and Not for me retain button weight. Details,
  MyAnimeList, and Hide are text actions; Later is the sole compact saved-state
  control. Details also opens on double-click or Enter. An overflow would reduce
  visible targets further, but it would also bury the Score Inspector—the exact
  behavior this release needs users to discover—so the hierarchy was fixed
  without hiding the differentiator.
