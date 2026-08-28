---
name: run-anirec
description: >-
  Launch and drive the AniRec PySide6 desktop app on Windows — start it, click
  through it with real input events, capture the window, and measure frame
  delivery or widget geometry. Use whenever you need to see a change working in
  the real app rather than in a test: "run AniRec", "screenshot the app", "does
  this actually work", "is this animation smooth", "check the layout at another
  size", or when verifying a UI fix before reporting it done.
---

# Running AniRec

A PySide6 desktop app. There is no browser, no dev server, and no Electron —
ignore any generic web or Electron run pattern. Everything below is verified on
this machine.

## The interpreter

Always the venv, never bare `python`:

```bash
./.venv/Scripts/python.exe
```

## Launch it

```bash
./.venv/Scripts/python.exe anirec_gui.py
```

Run it with `run_in_background: true` — it blocks in `app.exec()` until closed.
This starts the real entrypoint against the user's **real MyAnimeList account
and real local data**.

> Navigation, hovering and screenshots are safe. Do **not** click `RUN
> ANALYSIS`, `Recommend 5 more`, `Like`/`Not for me`, or anything in Settings →
> data actions unless the user asked for it: those mutate their profile, their
> saved state, or their MAL data.

Close it when finished so you don't leave a stray window:

```powershell
Get-Process -Name python | Where-Object { $_.MainWindowTitle -eq 'AniRec' } | Stop-Process -Force
```

## Two ways to drive it — pick deliberately

### 1. In-process driver (preferred)

Drives the real event loop with real input events, and can capture true
mid-animation frames because grabbing happens inside the process at a chosen
moment. This is the one to reach for.

The trick that makes it work: `gui_main.create_application()` **reuses an
existing `QApplication`**. So build the application first, schedule your driver
timers on it, then call `gui_main.main([])` — it reuses your instance, builds
the real window with real services, and enters `exec()` with your timers armed.

```python
import sys, time
sys.path.insert(0, r"C:/Users/bt.stajyer02/Documents/GitHub/AniRec")
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from AniRec import gui_main
from AniRec.gui.main_window import MainWindow, PageId

app = gui_main.create_application([])      # main() will reuse this
S = {"win": None}

def settle():
    S["win"] = next(w for w in QApplication.topLevelWidgets()
                    if isinstance(w, MainWindow))
    S["win"].resize(1280, 720)
    S["win"].grab().save("out/00.png")

def click(page_id):
    w = S["win"]
    QTest.mouseClick(w.navigation_buttons[page_id], Qt.MouseButton.LeftButton)
    print("page is now", w.current_page_id.value, flush=True)

QTimer.singleShot(2600, settle)            # services need ~2s to load
QTimer.singleShot(3400, lambda: click(PageId.LIBRARY))
QTimer.singleShot(4400, app.quit)

raise SystemExit(gui_main.main([]))
```

Notes that cost time to learn:

- **Give it ~2.5s before touching anything.** Services, theme and covers load
  asynchronously; act sooner and you drive a half-built window.
- **Print with `flush=True`.** Accumulating into a list and printing at the end
  interleaves confusingly with Qt's own output.
- **Wrap slot bodies in `try/except` and `traceback.print_exc()`.** PySide
  swallows exceptions raised inside a slot, so a broken driver looks like a
  driver that silently did nothing.
- **Assert the effect, don't assume it.** Print `w.current_page_id.value` after
  a click. A click that misses leaves the app on its start page (`discover`),
  which is easy to mistake for success.
- `w.grab()` costs ~100–160ms, so a grab loop cannot sample faster than ~6fps.
  That is the grab's cost, not the app's — measure frame rate the other way
  (below).

### 2. External process + Win32

Only when you specifically need the app as a separate process. Two traps:

- **Use `PrintWindow(hwnd, hdc, 2)`, not `Graphics.CopyFromScreen`.**
  `CopyFromScreen` captures whatever is on screen at those coordinates — if
  anything overlaps the window you will capture the user's other windows, which
  is both wrong and a privacy problem. `PrintWindow` reads the window's own
  buffer regardless of z-order.
- Client-to-screen coordinate maths for clicks is fiddly and easy to get
  silently wrong. Prefer the in-process driver.

## Screenshots without driving

There is already a deterministic harness. It uses the bundled sample library,
so images contain no personal data:

```bash
./.venv/Scripts/python.exe ./scripts/capture_docs_screenshots.py --output <dir> --theme dark
```

`--theme` takes `dark` or `light`. It writes Discover, My Library, Settings and
the first-run wizard. Adapt a copy of it (into a scratch dir, never the repo)
for other pages or window sizes.

**`QT_QPA_PLATFORM` must be `windows`.** The `offscreen` platform has no font
database and renders every string as empty boxes — any conclusion you draw
about layout from an offscreen render is worthless.

## Measuring, not eyeballing

### Frame delivery

Count real paint events over wall-clock time with an application event filter.
This is how you tell smooth from clunky:

```python
from PySide6.QtCore import QObject, QEvent
stamps = []
class Spy(QObject):
    def __init__(self): super().__init__(); self.on = False
    def eventFilter(self, o, e):
        if self.on and e.type() == QEvent.Type.Paint and isinstance(o, TargetClass):
            stamps.append(time.perf_counter())
        return False
```

Then take the **median gap** between stamps. ~16ms is 60fps; ~30ms+ reads as a
stutter.

The rule this app obeys: **opaque bounded widgets run at ~62fps; anything
translucent painted over content runs at ~18fps.** If a new animation is
choppy, that is almost always why.

### Geometry

Never claim clipping, misalignment or overflow from a screenshot — it is a
scaled PNG and antialiasing lies. Build the window offscreen-but-`windows`,
`show()`, `resize()` *after* `show()`, pump `processEvents()` a few times, then
print `x/y/width/height` and `font().pointSizeF()`.

## After changing the stylesheet

`AniRec/gui/qss_builder.py` and `AniRec/gui/design_tokens.py` are **sources**;
compiled copies ship in `AniRec/gui/resources/styles/*.qss`. Edit the source
without regenerating and `test_packaging_contract.py` fails:

```bash
./.venv/Scripts/python.exe ./scripts/build_theme.py
```

Painted (non-QSS) widgets read colours from application properties published in
`theme.py` (`resolvedAccent`, `resolvedWell`, `resolvedSidebar`, …). A new
painted colour needs publishing there — Qt's SVG renderer and `QPainter` have
no CSS cascade.

## The ACTIVITY console

`SystemLog.boot(entries)` paces a startup sequence one line per 130ms. While it
runs it sets `_booting = True`, and **every `append` in that window is queued
rather than printed**. Real startup traffic (vault load, palette bind, cover
fetches) lands in that window and can be swallowed.

If you are logging a genuine startup event, use `append` directly and reserve
`boot()` for an actual multi-line sequence. Verify by reading the console text
rather than trusting the call:

```python
from PySide6.QtWidgets import QPlainTextEdit
print(window.system_log.findChild(QPlainTextEdit).toPlainText())
```

Check it at ~400ms *and* after covers load — the deque holds `MAX_LINES = 200`,
and cover fetches add two lines per card.

Every line in this console must correspond to something that really happened,
with a real count where one exists. Do not add atmosphere lines.

## Tests

```bash
./.venv/Scripts/python.exe -m pytest tests/ -q -p no:randomly
```

The full suite takes **~65–70 minutes**; always background it. There is no
`pytest-timeout` plugin, so `--timeout` is a hard error.

For a fast UI check (~2–3 min):

```bash
./.venv/Scripts/python.exe -m pytest tests/test_appearance_and_layout.py tests/test_packaging_contract.py tests/test_gui_theme.py -q -p no:randomly
```

**Known pre-existing failure**, unrelated to any change you make:
`test_settings_page.py::test_data_actions_confirm_exact_scope_reset_ui_and_preserve_outside_sentinel`
compares `C:/Users/bt.stajyer02/...` against `C:/Users/BT4D2A~1.STA/...` — the
8.3 short name Windows generates because the username contains a dot. Treat the
suite as green at **1 failed, 530 passed**.

## Scratch files

Write probes and screenshots to the session scratchpad directory, never into
the repo.
