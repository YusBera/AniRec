from __future__ import annotations

import ast
import re
from pathlib import Path


TEXT_SUFFIXES = {
    ".example",
    ".gitignore",
    ".json",
    ".md",
    ".py",
    ".qss",
    ".spec",
    ".svg",
    ".toml",
    ".txt",
}
IGNORED_PARTS = {".git", ".venv", ".pytest_cache", "__pycache__", "build", "dist"}
CREDENTIAL_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}(?![0-9A-Fa-f])"),
    re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY-----"),
)
# Everything except the generic 32-hex rule, for files that legitimately
# contain hex identifiers.
HIGH_SIGNAL_PATTERNS = tuple(
    pattern
    for pattern in CREDENTIAL_PATTERNS
    if pattern.pattern != r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{32}(?![0-9A-Fa-f])"
)
STRUCTURAL_HEX_SUFFIXES = {".pdf"}

DEVELOPER_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:[\\/](?:Users|Github(?:%20| )projeleri)[\\/]|(?<![A-Za-z0-9])/(?:Users|home)/[^/{}\s]+/)",
    re.IGNORECASE,
)


def _audited_text_files(repo_root: Path):
    for path in repo_root.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.name == ".gitignore" or path.suffix.casefold() in TEXT_SUFFIXES:
            yield path


def test_repository_contains_no_real_credential_signatures(repo_root):
    findings = []
    for path in _audited_text_files(repo_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(text) for pattern in CREDENTIAL_PATTERNS):
            findings.append(path.relative_to(repo_root).as_posix())
    assert findings == []


def test_binary_assets_carry_no_credential_signatures(repo_root):
    """The text audit above skips images; images can still carry text.

    CHANGE [NO-CREDENTIALS]: a live MyAnimeList Client ID reached
    ``docs/images/anirec-settings.png`` and was committed, because the
    screenshot script built a window against the real application data root.

    Be clear about what this test does and does not catch. That leak was
    *drawn*, as pixels, and no byte scan can read it - only the capture-time
    isolation asserted below could have prevented it. What this catches is a
    credential arriving in an asset as bytes: a PNG tEXt/iTXt chunk, EXIF, an
    embedded path, a stray metadata write. A different vector, worth closing
    while we are here, and not a substitute for the one below.
    """
    findings = []
    for path in repo_root.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix.casefold() in TEXT_SUFFIXES or path.name == ".gitignore":
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        text = blob.decode("latin-1", errors="replace")
        # The bare 32-hex rule is right for source and wrong for formats that
        # store hex identifiers structurally: a PDF carries object ids, an /ID
        # array and font-subset checksums, all of which match it and none of
        # which are secrets. Those files are still checked against every
        # pattern that names a specific credential format.
        patterns = (
            HIGH_SIGNAL_PATTERNS
            if path.suffix.casefold() in STRUCTURAL_HEX_SUFFIXES
            else CREDENTIAL_PATTERNS
        )
        if any(pattern.search(text) for pattern in patterns):
            findings.append(path.relative_to(repo_root).as_posix())
    assert findings == []


def test_the_screenshot_script_cannot_read_the_real_profile(repo_root):
    """The capture script must keep isolating itself from real settings.

    This is the guard that actually corresponds to how the credential got
    out. ``MainWindow`` builds its own services for anything it is not
    handed, and those default to the live application data root - so a
    screenshot of the Settings page renders whatever account the operator has
    configured. The fix was to build every service against a throwaway root
    and blank the API fields before the grab; this fails if either defence is
    deleted, which is the only way it comes back.
    """
    script = repo_root / "scripts" / "capture_docs_screenshots.py"
    assert script.is_file()
    source = script.read_text(encoding="utf-8")

    assert "TemporaryDirectory" in source, "capture must use a throwaway data root"
    assert "root_override=" in source, "every service must be redirected"
    assert "_blank_api_fields" in source, "API fields must be cleared before the grab"
    assert "_assert_no_credentials" in source, "written images must be scanned"

    # The window must never be constructed bare: MainWindow(theme_manager=...)
    # alone is the exact call that read the real profile.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != "MainWindow":
            continue
        passed = {keyword.arg for keyword in node.keywords}
        assert "settings_service" in passed, (
            "MainWindow built without an isolated settings service"
        )


def test_runtime_and_public_docs_have_no_developer_absolute_paths(repo_root):
    roots = (repo_root / "AniRec", repo_root / "README.md", repo_root / ".env.example")
    findings = []
    for root in roots:
        paths = root.rglob("*") if root.is_dir() else (root,)
        for path in paths:
            if not path.is_file() or path.suffix.casefold() == ".pyc":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if DEVELOPER_PATH_PATTERN.search(text):
                findings.append(path.relative_to(repo_root).as_posix())
    assert findings == []


def test_production_code_does_not_execute_shell_commands(repo_root):
    findings = []
    for path in (repo_root / "AniRec").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                if any(name.split(".", 1)[0] == "subprocess" for name in names):
                    findings.append(f"{path.name}:subprocess")
            if isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr in {"system", "popen"}
                ):
                    findings.append(f"{path.name}:os.{node.func.attr}")
                if any(
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                    for keyword in node.keywords
                ):
                    findings.append(f"{path.name}:shell=True")
    assert findings == []


def test_gitignore_covers_every_local_runtime_and_build_scope(repo_root):
    lines = {
        line.strip()
        for line in (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {
        ".env",
        "config/",
        "token.json",
        "tokens/",
        "profiles/",
        "cache/",
        "logs/",
        "build/",
        "dist/",
        "release/",
    } <= lines
