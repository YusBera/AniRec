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

from AniRec.gui.css_tokens import build_tokens_css  # noqa: E402
from AniRec.gui.qss_builder import build_stylesheet, selectors  # noqa: E402


# Where the React frontend reads its variables from. One generated file, and
# the frontend's own stylesheets never name a hex value.
CSS_TOKENS_PATH = REPO_ROOT / "frontend" / "src" / "styles" / "tokens.css"


def main() -> int:
    STYLE_DIR.mkdir(parents=True, exist_ok=True)
    rendered = {}
    for theme in THEMES:
        stylesheet = build_stylesheet(theme)
        rendered[theme] = stylesheet
        path = STYLE_DIR / f"{theme}.qss"
        path.write_text(stylesheet + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(REPO_ROOT)} ({len(stylesheet.splitlines())} lines)")

    # The same tokens, for the other frontend. Written unconditionally so the
    # two can never be regenerated separately and drift.
    tokens = build_tokens_css()
    CSS_TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CSS_TOKENS_PATH.write_text(tokens, encoding="utf-8", newline="\n")
    print(
        f"wrote {CSS_TOKENS_PATH.relative_to(REPO_ROOT)} "
        f"({len(tokens.splitlines())} lines)"
    )

    first, second = (selectors(rendered[theme]) for theme in THEMES)
    if first != second:
        difference = sorted(first.symmetric_difference(second))
        print(f"themes disagree on {len(difference)} selectors: {difference}")
        return 1
    print(f"both themes style the same {len(first)} selectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
