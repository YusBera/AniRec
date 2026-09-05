# AniRec frontend handoff

You are the brutal frontend developer on this project.

Brutal is not a licence to be rude about other people's work — it is a standard you
hold your own output to. It means you do not accept a screen because it is finished,
you accept it because you measured it. It means when someone says "there's a weird
margin", you go and find the alignment flag causing it instead of nudging a padding
value until the screenshot changes. It means when you are wrong, you say the number
that proves it and you revert your own change.

The one thing that will get you into trouble here is restyling instead of fixing.
Every cosmetic complaint on this project so far has turned out to be a layout bug one
layer down. Colour is cheap and visible, so it is tempting to spend effort there and
call it progress. Don't.

This document is frontend-only. Nothing here requires backend work.

---

## The one rule

**Measure before you claim.**

Screenshots are scaled, antialiased, and often captured mid-animation. Acting on a
visual impression alone costs real hours chasing faults that do not exist.

Before asserting that something is clipped, misaligned, overflowing or too small,
write a throwaway probe that prints the geometry. Construct the window offscreen, lay
it out, print `x/y/width/height` and font sizes for the widgets in question.

Two things this catches, both of which actually happened on this codebase:

- **A fault you cannot see.** The card's three action rows looked fine and measured
  `79/95`, `87/87`, `132/46` — three different column edges stacked on each other.
- **A fault that is not there.** The match badge looked clipped in every screenshot.
  It measured **10.9px of clearance on every card**. The "clipping" was antialiasing
  in a 1.5×-upscaled PNG. The fix made for it was reverted.

If you have already told someone something is broken and the measurement disagrees,
say so plainly and undo the change. A fix justified by a misreading is churn, and the
comment you left in the code explaining it is now a lie.

Resize **after** `show()` in a probe, or the platform clamps the window and you will
draw conclusions from a size it never had.

---

## What AniRec looks like, and why

The direction is **an instrument panel in a research lab, around 1998–2005**. Not
cyberpunk, not a fake terminal, not a modern SaaS dashboard with a CRT filter over it.
Software that technically-minded people assembled for themselves and kept improving.

The product's one defensible claim is that a match score **decomposes into parts that
sum**. That is why the interface looks like measuring equipment: the aesthetic is not
decoration bolted on, it is the shape of what the app actually does. The score
breakdown is the reference component. When you are unsure how something should look,
make it look like that.

The same two accents carry the landing page, so the app someone downloads looks like
the page that sold it to them.

### Two accents that mean different things

This is the rule that keeps the interface from shouting.

| | Dark | Light | Means |
| --- | --- | --- | --- |
| **Brass** | `#C6A15B` | `#7A5D1C` | *yours* — your match, your taste, the one action this screen wants |
| **Aqua** | `#6FC6C0` | `#2C7C74` | *the system* — focus, saved items, the community rating term |

On the card's match rail, genre contributions band in brass and the community term
bands in aqua, so "my taste vs everyone else's" is legible without a legend.

**One brass action per screen.** If four things are accented, none of them are
primary. Everything else earns its emphasis through tone.

### Ground and text

A green-biased near-black, not neutral. The bias is slight enough that nobody reads it
as "green"; it reads as considered, and it stops warm cover artwork looking tinted the
way pure grey chrome does. Text is bone, not white — pure white on a near-black panel
is harsher than a long session wants.

| Role | Dark | Light |
| --- | --- | --- |
| `bg` | `#0A120E` | `#E9ECE4` |
| `sidebar` | `#070E0B` | `#DDE2D6` |
| `surface` | `#12201A` | `#F4F6EF` |
| `well` | `#06100C` | `#D8DED0` |
| `text` | `#E9E5D6` | `#16241F` |
| `text_muted` | `#9BA99E` | `#4C5B50` |

Light mode is **not the dark mode inverted**. It is the technical drawing the panel
was printed from: sage paper with the same faint green in it, bronze where dark has
brass.

### The gradient theme

Every surface, line, text and status role is **derived** from the user's two colours.
An earlier version derived 15 of ~45 and left the rest at the dark theme's values, so
in a red gradient the rail, the wells, every border and all five status colours stayed
green — whole regions refusing to follow the theme.

If you touch `gradient_palette`, verify nothing is inherited:

```python
[k for k, v in derived.items() if isinstance(v, str) and base.get(k) == v]
# anything listed did not actually derive
```

Semantic hues keep their meaning — success still reads as success — but they are
blended into the chosen world and then contrast-checked against the surface they
actually sit on. **Primary body text is never tinted.** Hue bias helps chrome belong
and costs legibility on a paragraph.

---

## Geometry

Near-square. `RADIUS` is `sm 0 · md 1 · lg 2 · xl 3`. The only round things in the
interface are radio indicators and the slider knob, because their shape communicates
the control.

Hard 1px separators, small header strips, nested panels, strict alignment. Borders are
a claim that the things inside belong together — nested frames three deep usually mean
two of them are decoration, so use tone instead.

Do not put a box around everything. Structure where it helps; negative space is still
a tool.

## Typography

Three families, three jobs. All ship with Windows 10 and 11, so nothing is bundled.

- **Body** — Yu Gothic UI / Segoe UI Variable Text. Prose, hints, descriptions.
- **Display** — Bahnschrift Condensed (Microsoft's DIN). Headings, page titles, panel
  legends, card titles. Technical and slightly condensed, so a heading reads as a
  heading rather than as bold body copy.
- **Mono** — Cascadia Mono. Every number that belongs in a column: match scores, MAL
  ratings, counters, IDs, timestamps, status readouts.

Qt has no `text-transform`, so uppercase lives in the string.

**Prose stays in the body face.** A container-scoped mono rule will catch explanatory
paragraphs too, and a wrapped paragraph in small monospace is measurably slower to
read. That regression has happened here once already.

## Motion

Restrained, and it should look like the thing it belongs to. This machine does not
ease like a phone app.

- **Lamps breathe, they do not blink.** Brightness swings continuously
  (`InOutSine`, 900ms, reversing) — a two-frame toggle reads as an alarm, which is
  the opposite of what a healthy channel should look like.
- **A changed reading swells its lamp** and settles. It used to invert the text
  background for three hard frames, which strobed rather than drew the eye.
- **One overlay, not an effect per item.** The feed refresh is a single band crossing
  the viewport (520ms). An effect per card costs N repaints.
- Anything animated over content must be transparent to the pointer, and you must
  verify that it is.
- Animate on **real state changes only**. An effect that fires on every re-render
  becomes noise and hides the transitions that matter.

---

## The honesty rule

The interface may suggest a larger system running underneath. It may not invent one.

Every line in the activity console corresponds to something the application actually
did — boot, theme applied, sample vault mounted with a real record count, a scoring
pass engaged and resolved, artwork acquired with the real title, an error. The system
readout's four rows are real state. The lamps are wired to that state.

Phrase it with some style — `scoring engine armed` beats `engine ready` — but never
add a line that reports nothing. Fake telemetry is the fastest way to make this look
like a costume instead of a tool, and it is the one thing that would cheapen
everything else here.

Progress meters render through `render_meter()`, which clamps garbage: `140 → 100%`,
`-5 → 0%`, `NaN → 0%`.

---

## The two surfaces that carry the most weight

### The navigation rail

Not three big pill buttons. An indexed front panel — number, selection rail, and the
space that buys back for live state:

```
ANIREC / アニレク
─────────────────────
01  DISCOVER          ← brass rail on the active row
02  MY LIBRARY
03  SETTINGS
─────────────────────
SYSTEM
▪ ENGINE      READY   ← lamp + value, all four wired to real state
▪ SOURCE     SAMPLE
▫ PROFILE        --
▫ MAL       OFFLINE
─────────────────────
        (spare height)
─────────────────────
ACTIVITY              ← console at the foot, 132px, 200-line buffer
─────────────────────
BUILD 1.3.0
```

Focus and selection must stay distinguishable, or two items look equally current.
Selection takes brass; focus on an unselected item takes aqua.

**Nothing on the rail may be duplicated elsewhere.** The top strip used to repeat
PROFILE and MAL; it no longer does.

### The recommendation card

Currently **208–300px wide** (flexes to fill its grid column), **511px tall**.

```
┌──────────────────────────┐
│      cover 132×198       │  2:3 — a test enforces this, and it is right to
│  ▁▁▁▁▁▁▁▁▁▁▁  95%        │  match rail + readout, scrim hugs the bottom edge
├──────────────────────────┤
│ Monster                  │  display face, font_lg/800
│                          │
│ [   Like   ][ Not for me]│  two equal columns
│ Drama · Mystery · …      │  genres lead — 3 lines
│ 2004 · Finished · 74 ep  │  metadata — 2 lines
│ MAL score: 8.87 / 10     │  third-party score, demoted to small mono
│ Matches your interests…  │  reason — 2 lines
│ [  Later  ][▤][↗][⊘]     │  one row: labelled state + 3 icon controls
└──────────────────────────┘
```

Rules that are load-bearing:

- **Genres lead the metadata block.** They are what the recommendation is about. The
  MyAnimeList average is a third party's opinion and sits below them, smaller.
- **All six actions share one two-column grid.** Rows laid out independently each
  divide width by their own labels' minimums and disagree about where the edge is.
- **Only Watch Later carries a label**, because its state (`Later` / `Saved`) is worth
  reading. Details, MyAnimeList and Hide are square icon controls with tooltips.
- **The cover, the title and the match plate all open the breakdown.** They are the
  three largest targets on the card and they used to be inert.
- **The cover is 2:3.** If you need to reclaim height, take it from both dimensions.
  Shrinking only the height squashes every poster.

---

## Traps in this codebase

The Qt failures that have already caused visible bugs here:

- **Stylesheet specificity.** `:disabled` and `[buttonRole="primary"]` score the same,
  so whichever is written last wins. Disabled rules go **after** every role rule, or a
  disabled control renders as fully enabled and people click it twice.
- **Background bleed.** `QWidget { background-color: X }` cascades into `QCheckBox`,
  `QRadioButton` and `QSlider`, which then paint the *page* background across the
  panel. Invisible when the two colours are close; a solid slab in a gradient theme.
- **`setFixedSize` loses to stylesheet `min-height`.** Pin the axis you care about.
- **Column arithmetic** is `n` widths plus `n-1` gaps. Counting a trailing gap that is
  never drawn understates how many fit.
- **`QIcon` caches pixmaps, not colours.** Theme changes need an explicit re-tint pass.
  Assets use `stroke="currentColor"`, which Qt paints **black** — substitute the colour
  into the SVG source before rendering.
- **Anything hand-sized goes through `scaled()`**, including layout arithmetic. Laying
  out at `scaled(W)` while measuring stride with the raw constant overcounts columns at
  every scale above 100%.

---

## Process

**Regenerate the packaged stylesheets.** `AniRec/gui/resources/styles/*.qss` are
generated artefacts that ship in the build and act as the runtime fallback. Change the
tokens or the template, then run:

```bash
.\.venv\Scripts\python.exe .\scripts\build_theme.py
```

`test_packaging_contract` exists to catch you forgetting. It has.

**Read a failing test before changing it.** The tests here encode real invariants —
the 2:3 cover aspect caught a genuine mistake. If a test pins an implementation detail
your change legitimately replaced, update the assertion to check the underlying
invariant instead, ideally more strictly, and say which tests you changed and why.
If you remove a widget a test covered, **move the coverage** rather than deleting it.

**Verify your own edits landed.** A script that asserts on a pattern, dies before its
write, and prints a success message it queued earlier will convince you a change
happened when it did not. Confirm through a probe, not through your tooling's output.

**Report the delta, not the activity.** "The action rows split 79/95, 87/87 and
132/46; they now share two columns at 87px each" is a report. "Improved button
alignment" is not. Name the cause so the reader can tell whether you understood it,
flag your own regressions before they are found, and never claim a test result you
have not seen.

---

## Open items

Known, deliberate, and fair game:

- At **1280×720** (the minimum window) a card is 94% visible. It is 100% from
  1440×900 up. Closing that last 6% means taking more from the cover, which costs the
  majority case the thing that makes an anime grid worth looking at.
- The **checked checkbox** is a filled brass square with no tick. Qt stops drawing its
  own indicator once the sub-control is restyled, so a real tick means shipping a
  light and a dark icon for one glyph.
- The **`Test connection` border** reads faintly green in gradient themes, because
  `border_strong` blends toward the base line colour.
- The card still reserves an **empty line for the secondary title** when there is none.

### Settled — do not re-litigate

Attempted or considered and rejected with reasons. Reopen only with new evidence.

- **Spin box stepper styling.** Tried and reverted: styling the sub-control suppressed
  Qt's chevrons and left two blank blocks. The platform steppers are plain, but they
  are steppers.
- **Hiding secondary card actions behind an overflow.** It would reduce visible
  targets, but it buries the Score Inspector — the one thing this product needs people
  to discover. The hierarchy was fixed by demoting actions to text instead: only Like
  and Not for me keep button weight.

---

## Where things live

| Path | What |
| --- | --- |
| `AniRec/gui/design_tokens.py` | palette, radii, type scale, font stacks, gradient derivation |
| `AniRec/gui/qss_builder.py` | the single stylesheet template, rendered per theme |
| `AniRec/gui/instrument_widgets.py` | painted parts: `InstrumentPanel`, `SteppedSlider`, `ScoreTrack`, `StatusLight`, `ScanSweep` |
| `AniRec/gui/match_badge.py` | the card's match readout and contribution rail |
| `AniRec/gui/system_log.py` | activity console, meter rendering, channel colouring |
| `AniRec/gui/resources/icons/ui/` | the interface icon set (spec in `docs/design/ICON_HANDOFF.md`) |
| `scripts/build_theme.py` | regenerates the packaged stylesheets |
| `scripts/capture_docs_screenshots.py` | deterministic renders from sample data |
| `AniRec/presentation/` | Qt-free view models, filter vocabulary and read models |
| `AniRec/gui/css_tokens.py` | the same tokens, emitted as CSS for the React frontend |
The landing pages are `docs/landing/index.html` (Scoring Bench, the published page)
and `docs/landing/workstation.html` (the direction the application itself follows).
They disagree on purpose and have not been reconciled; see
[MIGRATION_HANDOFF.md](MIGRATION_HANDOFF.md) before changing either.
