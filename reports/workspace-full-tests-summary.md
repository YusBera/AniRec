# Full Python verification

Full run completed after the desktop Profile cache repair.

- Command: `.venv/Scripts/python.exe -m pytest -q --tb=short -rA --junitxml=reports/workspace-full-tests.xml`
- Result: **738 passed, 2 failed; 740 tests total**.
- Duration: 4327.76 seconds (1 hour, 12 minutes, 7 seconds).
- Machine-readable result: `workspace-full-tests.xml` in this directory.

Failures:

1. `test_repository_contains_no_real_credential_signatures`: 6 dependency files.
2. `test_binary_assets_carry_no_credential_signatures`: 9 dependency/generated files.

Diagnostic rerun of the existing scan found all 15 paths under ignored
`frontend/node_modules/`. Every match used only the generic 32-hex-character
pattern; no AWS-key, GitHub-token, sk-prefix or private-key-header pattern matched.
No scanned file outside node_modules matched any credential pattern.

Inspected text contexts contain public Gist/Gravatar/GitHub identifiers, an HTTP
Content-MD5 example, a decimal calculation example and React/Scheduler numeric
comments. The scan's `IGNORED_PARTS` excludes Python environments and build output
but does not exclude node_modules. No application or test code was changed during
this verification, and the original full-suite failure result is preserved.

The two-real-account API integration check passed separately; see
`workspace-live-compare-check.json`. This verification did not create a branch,
commit or push, and did not update a handoff.
