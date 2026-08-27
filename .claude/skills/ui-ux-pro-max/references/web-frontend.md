# Web frontend traps

The same method as the desktop reference, applied where the framework differs.

## Contents

- [Measuring instead of eyeballing](#measuring-instead-of-eyeballing)
- [Theme derivation](#theme-derivation)
- [Layout slack](#layout-slack)
- [Type and hierarchy](#type-and-hierarchy)
- [Motion](#motion)
- [Interaction surfaces](#interaction-surfaces)
- [Avoiding the generated look](#avoiding-the-generated-look)

## Measuring instead of eyeballing

Read the rendered result, not the source. `getBoundingClientRect()` and
`getComputedStyle()` settle arguments that screenshots start.

    // does the row actually fill, or is slack piling on one side?
    [...document.querySelectorAll('.card')].map(el => {
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.x), w: Math.round(r.width) };
    })

Two traps specific to the browser:

- **Transitions freeze.** A tab that is not compositing returns mid-transition
  computed values. Inject `* { transition: none !important }` before reading colours.
- **Device pixel ratio.** A screenshot from a 1.5x display is upscaled; glyph edges
  look clipped when they are not. Confirm with numbers before "fixing" it.

## Theme derivation

The most common theme bug is a palette that derives only some of its roles. If a
theme is computed from user-chosen colours, check **every** role, not the obvious
ones — borders, wells, and the five status colours are where it silently keeps the
base theme's values and whole regions refuse to follow.

Enumerate and diff:

    Object.entries(derived).filter(([k, v]) => base[k] === v)
    // anything listed here did not actually derive

Keep semantic hues semantic. Success should still read as success; blend it toward the
theme so it belongs, then verify contrast against the surface it actually sits on.

Do not tint body text. A hue bias that helps chrome belong costs legibility on a
paragraph and buys nothing.

For CSS custom properties, define the full palette on bare `:root` and redefine only
the tokens inside media/attribute blocks. A colour whose *only* definition lives
inside `@media (prefers-color-scheme: dark)` does not apply in the unstamped default
state, and the page renders one theme's text on the other theme's ground.

## Layout slack

Grid and flex hide the same arithmetic as any other layout:

- `justify-content: flex-start` with fixed-width items dumps all leftover space on one
  edge. Use `repeat(auto-fit, minmax(min, 1fr))` when items should fill.
- `align-items: stretch` (the default) makes a short card in a row as tall as the
  tallest. `align-items: start` when they should size to content.
- A wrapped grid's last row stretching two items across the full width is why
  `minmax()` needs a max, not just a min.

Anything that can overflow — tables, code, diagrams — gets `overflow-x: auto` on its
own container so the page body never scrolls sideways.

## Type and hierarchy

- Running text near 65 characters. Set a scale and stay on it.
- The title of an item must not be smaller or lighter than its own metadata.
- `text-wrap: balance` on headings; letter-spacing on small uppercase labels.
- `font-variant-numeric: tabular-nums` anywhere digits line up in a column, or values
  jitter between rows and cannot be compared.
- Line-clamping (`-webkit-line-clamp`) silently truncates. Budget enough lines for the
  longest realistic content, not the sample.

## Motion

- Respect `prefers-reduced-motion` — collapse reveals to their end state, and disable
  smooth scrolling.
- One orchestrated entrance with staggered `animation-delay` reads as designed;
  scattered hover effects read as noise.
- Animate `transform` and `opacity`. Animating layout properties forces reflow per
  frame.
- Anything overlaying content needs `pointer-events: none` or it eats clicks.
- Prefer one animated overlay to an effect per item — N elements animating is N
  repaints.

## Interaction surfaces

- The whole obvious target should be clickable. If a card's image and title look like
  the way in, make them the way in — not just a small "details" link.
- Hit targets at least 24px, and matching what the element looks like.
- Every interactive element needs a visible `:focus-visible` state distinct from hover
  and from selection.
- Cursor should match behaviour — `pointer` on things that navigate.
- Never show the same state in two places on one screen.

## Avoiding the generated look

Generated designs cluster on a few tells. If your plan contains one and nothing in the
brief asked for it, change it:

- Inter or a single geometric sans doing every job.
- Purple-to-blue gradient hero on white.
- Warm cream with a serif display and a terracotta accent.
- Near-black with one neon accent.
- Everything centred, every corner rounded the same amount, an accent bar on every
  card, emoji as section markers.

The antidote is specificity: take the palette, the geometry and the vocabulary from
the subject's own world, and use structural devices (numbering, dividers, eyebrows)
only where they encode something true about the content. Numbered markers are right
for a real sequence and wrong as decoration.
