"""Stable source and PyInstaller entry point for the AniRec local API.

The sibling of ``anirec_gui.py``, and it exists for the same reason: a
PyInstaller entry script is executed as a top-level module with no package
context, so ``AniRec/api/__main__.py``'s relative imports cannot resolve
there. Running the package directly (``python -m AniRec.api``) still works
and is the documented development command; this is the file the bundle is
built from.
"""

from AniRec.api.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
