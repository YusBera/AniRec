# Qt / PySide traps

Concrete failure modes that cost real debugging time. Each one produced a visible bug
that looked cosmetic and was not.

## Contents

- [Stylesheet cascade](#stylesheet-cascade)
- [Background bleed](#background-bleed)
- [Sizing](#sizing)
- [Layout slack](#layout-slack)
- [Forms](#forms)
- [Native sub-controls](#native-sub-controls)
- [Icons and theme changes](#icons-and-theme-changes)
- [Scaling](#scaling)
- [Painted widgets](#painted-widgets)
- [Probing](#probing)

## Stylesheet cascade

Qt stylesheets follow CSS2 specificity. `QPushButton:disabled` and
`QPushButton[role="primary"]` score **the same**, so the one written last wins. Put
disabled/error rules after every role rule, or a disabled control keeps rendering as
fully enabled and users click it repeatedly.

Qt supports negated pseudo-states: `QPushButton:focus:!checked`. Use it when focus and
selection would otherwise render identically.

A rule that sets only `color` will not stop a broader rule from setting `font-family`.
If you scope a font to a container, prose inside that container inherits it too —
check that explanatory paragraphs did not become monospace.

Qt has no `text-transform`. Uppercase must be in the string.

## Background bleed

`QWidget { background-color: X }` cascades to every widget that does not override it.
`QCheckBox`, `QRadioButton` and `QSlider` will then paint the *page* background across
whatever panel they sit on. This is invisible when page and panel are near-identical
and becomes a solid slab the moment a theme pulls them apart.

    QCheckBox, QRadioButton, QSlider { background: transparent; }

Treat this as the first hypothesis whenever a control "refuses" a theme.

## Sizing

`setFixedSize()` does not beat a stylesheet `min-height`. Pinning both dimensions on a
control that a stylesheet also sizes leaves it shorter or taller than its neighbours
and vertically centred against them. Pin the axis you care about and let the row share
the other.

`QSizePolicy.Ignored` lets a widget shrink below its text width — useful to make a
grid own the width, but it clips labels rather than eliding them. Reduce padding to
buy the space back, and check the *longest* state of the label, not the initial one.

## Layout slack

Column count is `n` widths plus `n-1` gaps. Computing `available // (width + gap)`
counts a trailing gap that is never drawn and understates how many fit:

    columns = max(1, (available + gap) // (minimum + gap))

`layout.setAlignment(Qt.AlignLeft)` piles all leftover width against one edge. If
items should fill the row, drop the alignment and give the used columns equal stretch.

A `QGridLayout` stretches every cell to the tallest in its row. Pass `Qt.AlignTop`
when adding, or a short panel beside a tall one is drawn two-thirds empty.

Rows of paired buttons laid out independently each divide width by their own content's
minimum size, so their column edges disagree. Put them in one shared grid.

## Forms

`QFormLayout` at defaults gives every panel its own label-column width and alignment.
Configure it once and apply everywhere:

    form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

`QGroupBox::title` with `subcontrol-origin: margin` puts the title on the border, so
the frame line runs through the words. Use `subcontrol-origin: padding` with
`subcontrol-position: top left` and treat it as a section label inside the panel.

## Native sub-controls

Styling a sub-control makes Qt stop drawing its native part. Restyle
`QSpinBox::up-button` and the chevron disappears, leaving a blank block — you now owe
an `image:`. If you are not shipping icons for it, leave the sub-control alone.

`QSlider` and `QCheckBox::indicator` are unstyled by default and will render in the
platform highlight colour, which belongs to no theme. Style the groove, sub-page,
add-page and handle explicitly. A checked `QCheckBox::indicator` with a background but
no image has no tick — either ship the glyph or accept it reads as a filled toggle.

## Icons and theme changes

A `QIcon` holds rendered pixmaps, not a colour reference. Changing theme re-styles
every widget and leaves glyphs painted in the old theme's colour. Keep a re-tint pass
that clears the render cache and re-sets every icon, and call it wherever the theme is
applied.

SVGs authored with `stroke="currentColor"` are painted **black** by Qt's SVG renderer —
there is no CSS cascade. Substitute the colour into the SVG source text before
rendering, and render at several sizes rather than upscaling one raster.

## Scaling

If the project routes hand-chosen pixel sizes through a scale helper, every layout
calculation must use it too. Laying out at `scaled(WIDTH)` while measuring stride with
the raw constant overcounts columns at any scale above 100% and pushes the last one off
the edge. Verify by arithmetic across every scale the settings offer, not just 100%.

## Painted widgets

A widget cannot glow outside its own rectangle. If you want a halo, make the widget
larger than the mark and paint rings of falling alpha in the margin — QPainter has no
blur.

Overpainting gaps on a fill only works if the underlying colour is opaque. Over a
translucent scrim it tints rather than clears; draw the cells individually instead.

To animate a value smoothly, use `QVariantAnimation` and repaint. Toggling a stylesheet
property gives two hard frames, which reads as a strobe.

A widget with `WA_TransparentForMouseEvents` cannot receive hover. If it needs hover,
clear that attribute and explicitly `event.ignore()` presses so clicks still reach the
parent.

Filling a whole plate behind a short right-aligned string leaves most of the plate
covering nothing, which reads as an empty block over the artwork. Fit the fill to the
content — a gradient scrim under just the occupied edge.

## Probing

Construct the window offscreen, lay it out, print geometry. Resize **after** `show()`
or the platform may clamp it and you will draw conclusions from a size the window
never had.

    window.show()
    app.processEvents()
    window.resize(w, h)          # after show
    for _ in range(10): app.processEvents()

Useful probes: widget `x/y/width/height`, `font().pointSizeF()`, computed
`getComputedStyle`-equivalents via `widget.styleSheet()`, and hashing `widget.grab()`
to prove two states actually render differently.

Injecting `* { transition: none }` before reading computed colours avoids reading a
frozen mid-transition value in an environment that is not compositing.
