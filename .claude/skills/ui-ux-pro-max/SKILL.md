---
name: ui-ux-pro-max
description: >-
  Ruthless, evidence-driven UI/UX critique and redesign for desktop apps (Qt/PySide,
  Electron, native) and web frontends. Finds the structural cause of a visual problem
  instead of restyling over it, measures geometry before claiming anything, and
  separates real defects (clipping, misalignment, contrast failures, duplicated state,
  dead space) from matters of taste. Use this skill whenever the user asks you to
  redesign, critique, polish, "make it look better", "fix the UI", "overhaul" a screen,
  or complains that an interface looks generic, cluttered, unbalanced, cut off, or
  "AI-made" — and also when they hand you a screenshot and ask what is wrong with it,
  or ask for a design system, theme, or component restyle. Reach for it even when the
  request sounds like a small cosmetic tweak, because cosmetic complaints are usually
  symptoms of layout bugs underneath.
---

# UI/UX Pro Max

A method for redesigning interfaces so the fix lands on the cause, not the symptom.

The failure mode this exists to prevent: being handed a screenshot, adjusting colours
and spacing until it looks different, and declaring victory — while the actual faults
(a layout policy, a size hint, an unconfigured form, a background that bleeds) are
untouched and reappear the moment the window resizes or the theme changes.

## The core loop

1. **Reproduce it yourself.** Render the real screen. Never work from the user's
   description or from stale documentation screenshots alone.
2. **Measure before you claim.** Get numbers for the thing you think is wrong.
3. **Find the cause in layout/style code**, not in the paint that covers it.
4. **Change the cause. Re-measure. Compare to the number you started with.**
5. **Report the delta honestly**, including anything you broke on the way.

Steps 2 and 5 are what separate this from restyling. Do not skip them.

## Measure before you claim

Screenshots lie. They are scaled, antialiased, and captured mid-animation. Acting on
a visual impression alone will cost you real work chasing bugs that do not exist.

Before asserting that something is clipped, misaligned, overflowing, or too small,
write a throwaway probe that prints the geometry. In a Qt app that means constructing
the window offscreen, laying it out, and printing `x/y/width/height`, font sizes, and
computed style values for the widgets in question.

Two things this reliably catches:

- **Faults you cannot see.** Three action rows that look fine but measure `79/95`,
  `87/87`, `132/46` — three different column edges stacked on top of each other.
- **Faults that are not there.** A badge that looks clipped in a screenshot but
  measures with 10.9px of clearance on every card; the "clipping" was antialiasing in
  an upscaled PNG.

If you already told the user something was broken and the measurement disagrees,
say so plainly and undo the change you made for it. A fix justified by a
misreading is churn, and leaving it in means the comment in the code is a lie.

## Symptom → cause

Cosmetic complaints almost always have a structural cause one layer down. Train
yourself to translate:

| What the user says | What to actually look for |
| --- | --- |
| "there's a weird margin on the right" | container alignment flag dumping slack to one side; column-count arithmetic counting a trailing gap that is never drawn |
| "the buttons aren't aligned" | independent rows each dividing width by their own content's minimum size, instead of sharing one grid |
| "this widget rejects the theme" | a global background rule cascading into children that never override it; a derived palette that only re-derives some of its roles |
| "it's cut off" | a fixed line budget smaller than the wrapped text; a fixed height smaller than the content |
| "it looks empty / there's dead space" | a grid stretching every cell to the tallest in its row; a panel given stretch it should not have |
| "the form looks ragged" | form layout left at framework defaults — no label alignment, no field growth policy |
| "it doesn't look like the design" | derived values inherited from a base palette instead of being recomputed |

The give-away that you are about to restyle instead of fix: your intended change is a
colour, a font size, or a padding value, and the user's complaint was about
*position*, *size*, or *state*.

## Defects vs taste

Argue for taste; just fix defects. Keep them separate in your reporting so the user
knows which decisions are theirs.

**Defects** — objectively checkable, fix without asking:
clipped or elided text that had room, misalignment between elements that should share
an edge, contrast below WCAG AA for the text size, two controls showing the same state,
a disabled control that looks enabled, an interactive element with no affordance, a
control whose hit target is smaller than its visual, layout that breaks at a supported
window size or scale factor.

**Taste** — propose, explain the reasoning, accept the user's call:
palette, typeface pairing, density, ornament, motion style, metaphor.

When a user rejects your taste call, take it and move on. When they report a defect
you disagree with, measure it before disagreeing.

## Contrast and state

Check contrast numerically rather than by eye, especially for small text, muted
"subtle" tones, and any colour that is derived rather than authored. Derived palettes
are where contrast quietly fails: a role computed by blending toward a user-chosen
colour can land anywhere.

State must be legible without motion or interaction:
- Disabled must look disabled — and beware framework cascade order. In CSS-like
  systems (including Qt stylesheets) `:disabled` and an attribute selector can carry
  equal specificity, so whichever is written last wins. A disabled rule written first
  is silently overridden by every role rule after it.
- Focus and selection must be distinguishable from each other, or two items look
  equally current.
- Do not show the same fact twice on one screen. Pick the surface that owns it.

## Motion

Motion should look like the thing it belongs to. A lab instrument does not ease; a
consumer app does not strobe.

- Pick timing that matches the metaphor and stay consistent. Linear reads mechanical;
  ease-out reads modern; stepped reads digital.
- Prefer one widget animating over an effect applied per item. A single overlay
  sweeping a list costs one repaint; an effect per card costs N.
- Anything animated over content must not intercept input. Make it transparent to
  the pointer and verify that it is.
- Blinking reads as an alarm. If the state is normal (working, connected), animate
  brightness continuously instead of toggling two frames.
- Animate on real state changes only. An effect that fires on every re-render becomes
  noise and hides the transitions that matter.

## Density and hierarchy

- Count how much of the viewport is chrome before the first piece of real content.
  If it is more than a third, that is the finding.
- Rank the actions on a surface. Exactly one should carry the accent. If four things
  are accented, none of them are primary.
- The most important object should be the largest and heaviest. Check that a title is
  not smaller than its own metadata.
- Every panel border is a claim that the things inside belong together. Nested frames
  three deep usually mean two of them are decoration — replace them with tone.
- Labels earn their space. A caption that restates the value beside it is not a label,
  it is a word occupying pixels.

## Working in a codebase with tests

Existing tests often encode real design invariants. When one fails after your change,
read it before touching it — it may be protecting something you did not know mattered
(a cover's 2:3 aspect ratio, a batch cap, a scaling relationship).

Decide honestly which case you are in:

- **The test caught a real mistake.** Fix the code. Say so.
- **The test pins an implementation detail your change legitimately replaced.** Update
  the assertion to check the underlying invariant instead — ideally more strictly than
  before — and tell the user which tests you changed and why. Changing a test to make
  your own change pass is a serious move; it needs a stated reason every time.

If you remove a widget or behaviour that a test covered, move the coverage rather than
deleting it. The behaviour usually still exists somewhere else on screen.

## Derived and generated artefacts

Many projects generate something from the design source — compiled stylesheets, theme
files, icon sets, token exports — and ship the generated copy. Changing the source
without regenerating leaves the packaged build showing the previous design.

Search for a build or generate script near the design tokens and run it as part of
the change, not as an afterthought. A contract test that compares generated output to
source is a strong hint that this step exists.

## Verifying your own edits

When applying changes with a script, make the script fail loudly and verify the result
independently. A script that asserts on a pattern, dies before its write, and prints a
success message it queued earlier will convince you a change landed when it did not.

Confirm the change is in the file — or better, confirm the behaviour through a probe —
before reporting it. If a probe raises `AttributeError` for something you "added", the
edit never happened.

## Reporting

Lead with what you measured, not what you did.

- Give the before and after number: "the action rows split 79/95, 87/87 and 132/46;
  they now share two columns at 87px each."
- Name the cause, not just the fix, so the user can tell whether you understood it.
- List what you did not do and why, especially anything you judged out of scope.
- Flag your own regressions before the user finds them.
- Separate the defect fixes from the taste calls.

Do not claim a test result you have not seen. If a suite is still running, say so and
give the number when it lands.

## Reference

For platform-specific traps — Qt/PySide stylesheet cascade, layout policies, scaling —
read `references/qt-desktop.md`. For web, read `references/web-frontend.md`. Load only
the one that matches the target.
