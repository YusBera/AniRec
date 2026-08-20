# GUI asset licenses

`icons/anirec.svg`, its packaged `icons/anirec.ico` rendering, `images/anime-placeholder.svg`, and `images/anime-cover-placeholder.svg` are original assets created for AniRec. They are distributed under the repository's GNU General Public License v3.0 (GPL-3.0).

They do not reproduce or depend on artwork, characters, logos, or other assets from MyAnimeList or any anime title.

The vector assets use the colour roles defined in `AniRec/gui/design_tokens.py`, so the artwork and the interface share one palette.

`icons/anirec.ico` is generated from `icons/anirec.svg` by `scripts/build_icon.py`. Rebuild it there rather than editing it directly.

`styles/dark.qss` and `styles/light.qss` are generated. Edit `AniRec/gui/design_tokens.py` or the template in `AniRec/gui/qss_builder.py` and run `scripts/build_theme.py` rather than editing them directly.
