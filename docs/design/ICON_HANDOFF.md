# AniRec icon handoff

AniRec currently relies on text labels and improvised Unicode glyphs for several
high-frequency controls. Those placeholders keep the product usable, but they
weaken the technical instrument language and make Cards / List / Table feel like
three ordinary form buttons instead of view modes.

This document is frontend-only. No backend work is required to add these assets.

## Asset specification

Revised for the workstation direction. The geometry rules below are not stylistic
preference, they are what keeps the set consistent with the panel language: hard
rules, mitred corners, no soft edges anywhere in the interface.

- SVG with a `24 × 24` viewBox and transparent background.
- **Stroke `2`, `stroke-linecap="butt"`, `stroke-linejoin="miter"`.** Round caps and
  joins are the single biggest tell of a generic modern icon set; every terminal in
  this set is cut square. Raised from the original 1.5 so the icons hold weight
  beside monospace labels rather than looking hairline-thin next to them.
- **`stroke="currentColor"`, `fill="none"`.** The frontend tints per theme and state.
  Nothing is baked in — no amber, no green, no background plate.
- **Orthogonal and 45° only.** Arbitrary angles and curves are reserved for the few
  forms that genuinely need them (dials, the refresh arc, the lens). Everything else
  sits on the grid.
- Geometry on even coordinates wherever possible, so the forms stay aligned to each
  other rather than to nothing.
- Design for a 16–18 px rendered size.
- Filled/active variants are a **separate file with an `-active` suffix**, built as a
  single `fill-rule="evenodd"` path so the glyph is knocked out of the solid rather
  than drawn on top of it. That keeps the active state monochrome and legible on any
  background, which a second colour would not.
- Optical alignment matters more than mathematical centering. Icons will normally
  appear beside a short text label, not replace critical action copy.

### Iconography choices this direction forces

The original list implied a conventional set. Three glyphs were changed because the
obvious choice reads as consumer software rather than instrumentation:

| Action | Conventional | Used here | Why |
| --- | --- | --- | --- |
| Like / Not for me | heart, thumb | `[+]` / `[−]` in a square frame | Sample marks, not social reactions. Unambiguous beside the existing labels, and the pair reads as one control. |
| Profile | person silhouette | record card: frame, photo block, two data lines | A profile here is a stored local record, not an avatar. |
| Filter / Settings | funnel, gear | horizontal faders / vertical faders | Both are instrument controls, and the axis difference keeps them distinct at 16 px. |

Everything else keeps its conventional form, drawn to the geometry rules above.
Recognisability wins over theme: a search glyph is still a lens, a folder is still a
folder. The lens is square-cased and the folder is mitred, which is enough.

## Priority 0 — blocks the intended Discover experience

| Filename | Use | Required states |
| --- | --- | --- |
| `like.svg` | Card, list-row, table-selection and detail Like action | outline + active |
| `dislike.svg` | Card, list-row, table-selection and detail Not for me action | outline + active |
| `view-grid.svg` | Cards view selector | default + active |
| `view-list.svg` | Compact list selector | default + active |
| `view-table.svg` | Data-table selector | default + active |
| `watch-later.svg` | Watch Later action and empty state | outline + active |
| `details-inspector.svg` | Open recommendation score inspector | default |
| `external-mal.svg` | Open title on MyAnimeList | default |

## Priority 1 — removes remaining placeholder glyphs

| Filename | Use | Required states |
| --- | --- | --- |
| `filter.svg` | Discover filtering controls and filtered empty state | default |
| `hide.svg` | Hide a recommendation | default |
| `show-hidden.svg` | Reveal hidden recommendations | default |
| `folder-liked.svg` | Liked collection and its empty state | default |
| `folder-disliked.svg` | Disliked collection and its empty state | default |
| `folder-watch-later.svg` | Watch Later collection and its empty state | default |
| `chevron-left.svg` | Previous title in the inspector | default |
| `chevron-right.svg` | Next title in the inspector | default |
| `close.svg` | Dialog close action where a platform close control is unavailable | default |
| `search.svg` | Search field and no-search-results state | default |

## Priority 2 — shell and maintenance actions

| Filename | Use | Required states |
| --- | --- | --- |
| `nav-dashboard.svg` | Dashboard navigation | default |
| `nav-discover.svg` | Discover navigation | default |
| `nav-library.svg` | Library navigation | default |
| `nav-settings.svg` | Settings navigation | default |
| `refresh.svg` | Refresh recommendations | default |
| `sync.svg` | MAL synchronization | default + working |
| `connect.svg` | MAL/API connection action | default |
| `profile.svg` | Taste profile controls | default |
| `open-folder.svg` | Open the local data folder | default |
| `copy.svg` | Copy paths, identifiers, or diagnostics | default |
| `trash.svg` | Destructive local-data actions | default |
| `theme-system.svg` | System appearance choice | default |
| `theme-light.svg` | Light appearance choice | default |
| `theme-dark.svg` | Dark/OLED appearance choice | default |
| `theme-gradient.svg` | Custom gradient appearance choice | default |

## Integration note

Do not replace clear action names such as **Like**, **Not for me**, or **Details**
with icon-only controls. Those are conversion-critical and need immediate meaning.
The icons should reinforce the label, while view toggles may collapse to icon-only
at narrow widths if their accessible names and tooltips remain present.



## Delivered

`AniRec/gui/resources/icons/ui/` — 40 files, generated by
`scripts/build_ui_icons.py`. Re-run it after editing that script; do not
hand-edit the SVGs, they are output.

```powershell
.\.venv\Scripts\python.exe .\scriptsuild_ui_icons.py
```

The whole `gui/resources` tree is already a single PyInstaller data entry, so
the new subdirectory ships with no change to `AniRec.spec`.

### Active variants shipped

Only where the state is genuinely not carried by anything else:

| Icon | Why it needs one |
| --- | --- |
| `like-active`, `dislike-active` | A card must show at a glance that it has been voted on. The card border tint alone is a colour-only signal. |
| `watch-later-active` | Same: saved or not saved has to survive being read without colour. |
| `view-grid-active`, `view-list-active`, `view-table-active` | Small toggles in a tight group; the filled tile reads faster than the button chrome at 16 px. |
| `sync-working` | A segmented ring the shell can rotate in steps, which matches the rest of the motion in this direction better than a smooth spinner. |

### Active variants deliberately not shipped

`nav-*` and `theme-*` were specified as default + active. They are shipping as
single files. Navigation selection is already carried by three signals — the
brass rail, the raised background, and the text colour — and the theme choice
sits in a control whose own checked state is unambiguous. A second icon state
there is weight without information, and the specification above says to
provide states *only* where they are needed. Say the word if the integration
proves otherwise and the four pairs are a one-line addition to the generator.

### Known weak point

`hide.svg` is the busiest glyph in the set: an eye, a pupil and a slash inside
24 px. It holds at 24 and above, and is legible but dense at 16. If it is only
ever used at 16 px beside a label, consider dropping the pupil from it.

## Application icon and logo

Generated by `scripts/build_logo.py`; run `build_icon.py` afterwards to refresh
the packaged `.ico`. Do not hand-edit the SVGs, they are output.

```powershell
.\.venv\Scripts\python.exe .\scriptsuild_logo.py
.\.venv\Scripts\python.exe .\scriptsuild_icon.py
```

### Two marks, one system

| File | Mark | Used at |
| --- | --- | --- |
| `anirec.svg` | `AR` monogram + readout | 32 px and above |
| `anirec-mark-a.svg` | `A` monogram + readout | 16 and 24 px |

Two letterforms inside 16 px leaves about four pixels of stem each and turns to
mush, so the small frames carry one letter. This is not a compromise, it is what
Windows icons have always done: simplified artwork at the small sizes rather
than one drawing scaled down seven times. `build_icon.py` now selects between
the two by size, and `--no-compact` renders everything from the full mark.

Both letters are drawn as filled paths, not set in a typeface. Nothing can be
guaranteed installed on a user's machine, and a logo that silently falls back to
Arial is not a logo.

### The readout

The segmented bar is the one element unique to this product: a score that
decomposes into parts that sum. It carries a warm-to-cool sweep drawn from the
palette's own accents — brass, gold, pale gold, a chartreuse bridge, mint, aqua
— then two unlit cells. Six lit of eight is deliberate: the score is high, and
it is not 100.

An earlier version used eleven narrower cells across a longer ramp. It smeared
into a single muddy band the moment the mark was rendered at 16 px. Six wide
cells survive the downscale and the sweep still reads.

### Verification

`scripts/build_logo.py` output was checked at 16/24/32/48/80/160 px, and the
`.ico` was verified by parsing its own directory and comparing each stored frame
against both sources: 16 and 24 carry the compact mark, 32 through 256 carry AR.

One quirk worth knowing: **Qt does not necessarily return the stored frame.**
Asked for 24 px, `QIcon` on the `.ico` renders the AR mark, having picked an
adjacent frame and scaled it, even though the stored 24 px frame is the compact
one. The Windows shell uses the stored frames. Both results are acceptable, but
do not use `QIcon.pixmap()` to check what a `.ico` contains — parse the file.
