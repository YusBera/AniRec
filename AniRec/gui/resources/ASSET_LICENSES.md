# GUI asset licenses

`icons/anirec.svg`, its packaged `icons/anirec.ico` rendering, `images/anime-placeholder.svg`, and `images/anime-cover-placeholder.svg` are original assets created for AniRec. They are distributed under the repository's GNU General Public License v3.0 (GPL-3.0).

They do not reproduce or depend on artwork, characters, logos, or other assets from MyAnimeList or any anime title.

The vector assets use the colour roles defined in `AniRec/gui/design_tokens.py`, so the artwork and the interface share one palette.

`icons/anirec.ico` is a rendering of `icons/anirec.svg` and still carries the previous palette. Regenerate it from the SVG at 16, 24, 32, 48, 64, 128, and 256 pixels when convenient.

`styles/dark.qss` and `styles/light.qss` are generated. Edit `AniRec/gui/design_tokens.py` or the template in `AniRec/gui/qss_builder.py` and run `scripts/build_theme.py` rather than editing them directly.
