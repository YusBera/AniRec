# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).resolve()
package_root = project_root / "AniRec"
resources = package_root / "gui" / "resources"
icon = resources / "icons" / "anirec.ico"
version_info = project_root / "packaging" / "windows_version_info.txt"

a = Analysis(
    [str(project_root / "anirec_gui.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(resources), "gui/resources"),
        (str(project_root / "LICENSE"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PIL",
        "_pytest",
        "numpy.testing",
        "numpy.tests",
        "pandas.tests",
        "pygments",
        "pytest",
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
    name="AniRec",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon),
    version=str(version_info),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AniRec",
)
