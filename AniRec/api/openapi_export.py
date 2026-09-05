"""Print the OpenAPI document, deterministically, for type generation.

    python -m AniRec.api.openapi_export > schema.json

Determinism matters because the output feeds a generated, committed
TypeScript file: a schema whose key order wandered between runs would show
up as a diff on every regeneration and make "are the types in sync?"
unanswerable. Two things secure it - ``sort_keys`` on the dump, and building
the app against a throwaway data directory so nothing about the developer's
own profile, settings or synced library can reach the document.

The app is built without a token deliberately. ``create_app`` disables
``/openapi.json`` when one is required (see its docstring), and the schema is
a build-time artefact rather than something a running packaged process should
serve.
"""

from __future__ import annotations

import json
import sys
import tempfile

from .app import create_app


def build_schema() -> dict:
    """The OpenAPI document, from an app wired to a disposable data root."""
    with tempfile.TemporaryDirectory(prefix="anirec-openapi-") as scratch:
        return create_app(root_override=scratch).openapi()


def main() -> int:
    json.dump(build_schema(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
