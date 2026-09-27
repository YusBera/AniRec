# Design reference captures

Screenshots and notes behind D-016 (the latest PySide client is the design
reference for the web client). Captured on 2026-09-24 from the labelled sample
library only. No real profile was used and no credential was entered; the API
setup screenshot shows empty fields.

| Folder | What it is |
| --- | --- |
| `pyside-latest/` | The latest PySide client (`AniRec/gui` at the commit these were taken from), 23 states at 1440×900 and 1024×768, with `NOTES.md` describing each surface's structure, controls and exact strings. **This is the target.** |
| `react-before-port/` | The React client before the port, the same sample data, with `NOTES.md` and measured card geometry. This is the "before" picture; do not copy it. |
| `tools/capture_pyside.py` | The offscreen capture script used for `pyside-latest/`. |

The notes mention local scratch paths from the machine that produced them;
those paths no longer matter.

## Re-capturing PySide safely

Run the desktop client **offscreen**, with its app-data folder redirected to an
empty scratch folder, so it can never read or rewrite a real profile:

```bash
export QT_QPA_PLATFORM=offscreen
export APPDATA=/tmp/anirec-capture-appdata   # the script asserts isolation; adjust its check
export LOCALAPPDATA=$APPDATA
python docs/reference/tools/capture_pyside.py
```

The script asserts that `APPDATA` contains `pyside-latest-appdata`. Keep an
equivalent check if you edit it. Use the app's "Look around with sample data"
path only, and never type a MyAnimeList Client ID or secret into a capture.
