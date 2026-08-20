"""Regenerate the packaged stylesheets from the design tokens.

Run after changing ``AniRec/gui/design_tokens.py`` or the template in
``AniRec/gui/qss_builder.py``:

    .\\.venv\\Scripts\\python.exe .\\scripts\\build_theme.py

The application renders its stylesheet at runtime so that font sizes follow the
user's scale setting. The files written here are the reference copy of the same
output: they are what ships in the package, what the acceptance script checks
for, and the fallback if generation ever fails.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STYLE_DIR = REPO_ROOT / "AniRec" / "gui" / "resources" / "styles"
THEMES = ("dark", "light")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from AniRec.gui.qss_builder import build_stylesheet, selectors  # noqa: E402


def main() -> int:
    STYLE_DIR.mkdir(parents=True, exist_ok=True)
    rendered = {}
    for theme in THEMES:
        stylesheet = build_stylesheet(theme)
        rendered[theme] = stylesheet
        path = STYLE_DIR / f"{theme}.qss"
        path.write_text(stylesheet + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(REPO_ROOT)} ({len(stylesheet.splitlines())} lines)")

    first, second = (selectors(rendered[theme]) for theme in THEMES)
    if first != second:
        difference = sorted(first.symmetric_difference(second))
        print(f"themes disagree on {len(difference)} selectors: {difference}")
        return 1
    print(f"both themes style the same {len(first)} selectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
