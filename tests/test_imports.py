from __future__ import annotations

import os
import subprocess
import sys


# Importing the GUI package takes about 1.5s on an idle machine. The bound is
# here to stop a hung import from stalling the run, not to assert a speed, so
# it is generous: with the whole suite competing for the CPU a 10s bound turned
# a correctness test into a machine-load test.
SUBPROCESS_TIMEOUT_SECONDS = 90

def test_direct_script_entrypoint_exits_cleanly(repo_root):
    result = subprocess.run(
        [sys.executable, str(repo_root / "AniRec" / "main.py")],
        input="3\n",
        text=True,
        capture_output=True,
        cwd=repo_root,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0
    assert "Goodbye." in result.stdout


def test_package_module_entrypoint(repo_root):
    result = subprocess.run(
        [sys.executable, "-m", "AniRec.main"],
        input="3\n",
        text=True,
        capture_output=True,
        cwd=repo_root,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Goodbye." in result.stdout


def test_cli_module_entrypoint(repo_root):
    result = subprocess.run(
        [sys.executable, "-m", "AniRec.cli"],
        input="3\n",
        text=True,
        capture_output=True,
        cwd=repo_root,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Goodbye." in result.stdout


def test_gui_module_import_has_no_side_effects(repo_root):
    result = subprocess.run(
        [sys.executable, "-c", "import AniRec.gui_main"],
        text=True,
        capture_output=True,
        cwd=repo_root,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_gui_module_exits_cleanly_when_event_loop_is_stopped(repo_root):
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    script = (
        "from PySide6.QtCore import QTimer; "
        "from AniRec.gui_main import create_application, main; "
        "app = create_application([]); "
        "QTimer.singleShot(0, app.quit); "
        "raise SystemExit(main([]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        cwd=repo_root,
        env=environment,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
