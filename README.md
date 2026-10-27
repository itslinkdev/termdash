# termdash

A visual terminal dashboard for Python 3.11+ and Textual. **All readings are
simulated**: the app never inspects your CPU, repository, disk, or network and
never requests weather data.

## Run

From this folder, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m termdash --demo
```

With an activated environment, use `python -m termdash --demo`.
Running without `--demo` prints usage; real providers are not implemented.

The header shows the local clock. The 2×2 grid contains CPU/memory sparklines,
weather, Git status, and network/disk bars. It fits 80×24 terminal cells and
expands to 200×60. Sparklines show 48 samples, automatically scaled to their
own range; network bars use a simulated 100 Mb/s link, and disk uses 256 GiB.

| Key | Action |
| --- | --- |
| `q` | Quit |
| `t` | Cycle dark → light → high-contrast retro green → dark |
| `r` | Refresh demo values immediately |
| `?` | Open or close help |
| `Esc` / `Enter` | Close help |

Values refresh every two seconds; the clock updates every second.
All application styling and palette variables are in `termdash/styles.tcss`.
The terminal controls the font and must support Unicode border/chart glyphs.
Textual respects `NO_COLOR`; unset that environment variable to see the palettes.

## Structure

- `termdash/app.py`: composition, clock, refresh, keyboard actions, help.
- `termdash/data.py`: immutable panel data and random, bounded `DemoProvider`.
- `termdash/providers/`: typed `Provider` protocol with `fetch()` returning a
  dataclass, and `SystemProvider` using psutil. System samples include per-core
  CPU, 48-sample CPU/memory histories, disk usage, and network bytes/s from
  counter deltas divided by monotonic elapsed time. The first network rate is
  zero while establishing a baseline. CPU measures a 0.1-second window.
  Live providers are not connected to the dashboard yet.
- `termdash/panels/`: one widget class per file, each accepting a reactive `data`
  attribute. Assign a fresh matching data object to update a panel; widgets have
  no knowledge of the provider. A future provider can return the same `Snapshot`.
- `termdash/styles.tcss`: geometry, rounded borders, padding, all three themes.
- `tests/test_app.py`: standard-library unittest with Textual Pilot.
- `docs/termdash-retro.svg`: Pilot screenshot after pressing `t` twice at 80×24.

## Build and test

This source-only Python app has no separate bundling step. Compile-check it and
run the tests (pytest and psutil are included in `requirements.txt`):

```powershell
.\.venv\Scripts\python.exe -m compileall -q termdash tests
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

The Pilot test boots the app, cycles themes twice, and rewrites the SVG in
`docs/`. Additional checks cover theme wraparound, quit, help, refresh, reactive
updates, simulated-value bounds, and panel geometry at 80×24, 120×36, and 200×60.
Screenshot tests temporarily unset `NO_COLOR` so the SVG captures theme colors.

## Limits

Demo data only; no live integrations or theme persistence. Layouts smaller than
80×24 are not supported. Real-provider error/loading states are not implemented.
SVG snapshots contain the current clock, so regenerating them changes the file.

MIT licensed. Copyright holder: TODO.
