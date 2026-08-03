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
