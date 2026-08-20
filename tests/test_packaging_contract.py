from __future__ import annotations

import struct

from AniRec import __version__


def test_release_version_launcher_and_spec_are_consistent(repo_root):
    assert __version__ == "2.0.0"
    launcher = (repo_root / "anirec_gui.py").read_text(encoding="utf-8")
    spec = (repo_root / "AniRec.spec").read_text(encoding="utf-8")

    assert "from AniRec.gui_main import main" in launcher
    assert 'console=False' in spec
    assert '"gui/resources"' in spec
    assert '"LICENSE"' in spec
    assert 'icon=str(icon)' in spec
    assert 'version=str(version_info)' in spec


def test_packaged_icon_contains_multiple_windows_icon_sizes(repo_root):
    icon = repo_root / "AniRec" / "gui" / "resources" / "icons" / "anirec.ico"
    payload = icon.read_bytes()
    reserved, image_type, image_count = struct.unpack("<HHH", payload[:6])

    assert reserved == 0
    assert image_type == 1
    assert image_count >= 7


def test_build_script_uses_clean_tracked_spec_and_checks_expected_executable(repo_root):
    script = (repo_root / "scripts" / "build_windows.ps1").read_text(
        encoding="utf-8"
    )

    assert "PyInstaller --noconfirm --clean" in script
    assert '"AniRec.spec"' in script
    assert '"dist\\AniRec"' in script
    assert '"AniRec.exe"' in script
    assert '"README.md"' in script
    assert "Remove-Item" not in script


def test_readme_documents_only_the_verified_desktop_release(repo_root):
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    required_sections = (
        "## Desktop application",
        "## Run from source",
        "## MyAnimeList setup",
        "## Run the Windows package",
        "## Build the Windows package",
        "## How recommendations are made",
        "## Command-line interface",
        "## Local data and privacy",
        "## Tests",
        "## Troubleshooting",
        "## License and attribution",
        "## Known limitations in 2.0.0",
    )

    assert all(section in readme for section in required_sections)
    assert "currently a CLI workflow" not in readme
    assert "There is no automated test suite" not in readme
    assert "onefile" in readme and "not shipped" in readme
    assert "second Windows 10/11 computer acceptance run is still required" in readme
    for name in (
        "anirec-first-run-wizard.png",
        "anirec-home.png",
        "anirec-recommendations.png",
        "anirec-settings.png",
    ):
        assert (repo_root / "docs" / "images" / name).is_file()


def test_second_computer_acceptance_tooling_is_hash_verified_and_non_destructive(
    repo_root,
):
    verifier = (repo_root / "scripts" / "verify_windows_acceptance.ps1").read_text(
        encoding="utf-8"
    )
    packager = (repo_root / "scripts" / "package_windows_acceptance.ps1").read_text(
        encoding="utf-8"
    )
    template = (repo_root / "docs" / "USER_ACCEPTANCE_TEMPLATE.md").read_text(
        encoding="utf-8"
    )

    assert "SHA256SUMS.csv" in verifier
    assert "Get-FileHash" in verifier
    assert "Manifest path safety" in verifier
    assert "No-console GUI subsystem" in verifier
    assert "Start-Process" in verifier and "[switch]$Launch" in verifier
    assert "Compress-Archive" in packager
    assert "Export-Csv" in packager
    assert "Remove-Item" not in verifier
    assert "Remove-Item" not in packager
    assert template.count("|  |  |") >= 16
    assert "PASS`, `FAIL`, or `BLOCKED" in template


def test_release_version_is_recorded_in_the_windows_resource(repo_root):
    resource = (repo_root / "packaging" / "windows_version_info.txt").read_text(
        encoding="utf-8"
    )

    assert f"'FileVersion', '{__version__}'" in resource
    assert f"'ProductVersion', '{__version__}'" in resource
    numeric = ", ".join(__version__.split(".") + ["0"])
    assert f"filevers=({numeric})" in resource
    assert f"prodvers=({numeric})" in resource


def test_generated_stylesheets_match_their_source(repo_root):
    """The packaged themes must be a current rendering of the design tokens.

    They are generated artefacts. Editing one by hand, or changing the tokens
    without rebuilding, would ship a stylesheet that no longer matches what the
    application renders at runtime.
    """
    from AniRec.gui.qss_builder import build_stylesheet

    for theme in ("dark", "light"):
        packaged = (
            repo_root / "AniRec" / "gui" / "resources" / "styles" / f"{theme}.qss"
        ).read_text(encoding="utf-8")
        assert packaged.strip() == build_stylesheet(theme).strip()
