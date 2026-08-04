from __future__ import annotations

import builtins

import pytest

from main import (
    get_profile_dir,
    print_user_friendly_error,
    prompt_int,
    require_file,
    safe_profile_name,
)


@pytest.mark.parametrize(
    ("username", "expected"),
    [
        ("normal.user-1", "normal.user-1"),
        ("  ../Yusuf Bera/..", "Yusuf_Bera"),
        ("...", "mal_user"),
        ("Çığ", "mal_user"),
    ],
)
def test_safe_profile_name_characterizes_current_sanitizing(username, expected):
    assert safe_profile_name(username) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [("", 5), ("invalid", 5), ("0", 5), ("11", 5), ("7", 7)],
)
def test_prompt_int_defaults_and_range(monkeypatch, raw_value, expected):
    monkeypatch.setattr(builtins, "input", lambda _prompt: raw_value)
    assert prompt_int("Value", default=5, minimum=1, maximum=10) == expected


def test_require_file_returns_existing_path_and_explains_missing(system_temp_dir):
    existing = system_temp_dir / "existing.csv"
    existing.touch()
    assert require_file(existing, "Run the prior step.") == existing

    missing = system_temp_dir / "missing.csv"
    with pytest.raises(FileNotFoundError, match="Run the prior step"):
        require_file(missing, "Run the prior step.")


def test_profile_dir_uses_injected_app_data_root(system_temp_dir):
    result = get_profile_dir("Fixture User", root_override=system_temp_dir / "app-data")
    assert result == (
        (system_temp_dir / "app-data").resolve() / "profiles" / "Fixture_User"
    )


def test_unexpected_cli_error_is_short_and_does_not_expose_raw_secret(capsys):
    print_user_friendly_error(RuntimeError("client_secret=fixture-secret"))

    output = capsys.readouterr().out
    assert "AniRec could not complete the operation" in output
    assert "Suggested action:" in output
    assert "fixture-secret" not in output
    assert "Traceback" not in output
