# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the API sidecar a desktop shell would spawn.

NOTHING SPAWNS THIS YET. There is no Tauri application in this repository -
see frontend/README.md, "What is not here yet". This spec exists so the
Python payload could be measured before committing to a desktop shell, and
that measurement is the point: 85 MB built and verified serving the real
feed, against the PySide package's 178 MB.

The point of comparison for the whole Tauri experiment: this bundle is
AniRec's Python payload *without* a GUI toolkit. It carries the services,
the scoring engine, pandas and the HTTP stack; it explicitly excludes
PySide6 and shiboken6, which is the single largest line item in the current
desktop package.

``console=True`` is required, not cosmetic: the startup handshake in
``AniRec/api/__main__.py`` is a line on stdout, and a windowed build has no
stdout to write it to. The shell is responsible for spawning this with
CREATE_NO_WINDOW on Windows so no console flashes at the user - see
src-tauri/src/backend.rs.

UPX is off here for the same reason it was turned off in AniRec.spec: it is
a well-known antivirus heuristic trigger and buys little against a payload
this size.
"""

from pathlib import Path


project_root = Path(SPECPATH).resolve()
package_root = project_root / "AniRec"
resources = package_root / "gui" / "resources"

a = Analysis(
    [str(project_root / "anirec_api.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # The sample library lives under gui/resources by history, not by
        # dependency: SampleDataService reads it through resource_path and
        # imports nothing from the GUI. Moving it is a separate change.
        (str(resources / "sample"), "gui/resources/sample"),
        (str(project_root / "LICENSE"), "."),
    ],
    hiddenimports=[
        # uvicorn resolves these by string at runtime, so static analysis
        # does not see them.
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # The entire reason this bundle is smaller than the desktop one.
        "PySide6",
        "shiboken6",
        "PIL",
        "_pytest",
        "numpy.testing",
        "numpy.tests",
        "pandas.tests",
        "pygments",
        "pytest",
        "tkinter",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="anirec-api",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="anirec-api",
)
