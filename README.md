# termdash

A terminal dashboard for Python 3.11+ and Textual. Live mode reads local CPU,
memory, disk, network and Git data. `--demo` keeps all readings simulated.
**Weather is always simulated**, including in live mode. No provider makes
network requests or changes your repository.

GIF preview: TODO (record a short terminal session).

## Run

From this folder, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\termdash.exe
```

Git must be installed and available on PATH. Choose a repository and polling
delays (positive, finite seconds):

```powershell
.\.venv\Scripts\python.exe -m termdash --repo "D:\path\to\repo" --system-interval 1 --git-interval 5
.\.venv\Scripts\python.exe -m termdash --demo --demo-interval 2
.\.venv\Scripts\python.exe -m termdash --help
```

CLI flags override the TOML settings. `git.repo` defaults to the current working
directory. Defaults are 2 seconds for
system data, 5 seconds for Git, and 2 seconds for demo/weather data. Each delay
starts after that provider's fetch finishes. Pressing `r` wakes waiting workers;
an in-flight fetch finishes before the next fetch starts.

The header shows the local clock and LIVE or DEMO mode. The 2×2 grid fits 80×24
terminal cells and expands to 200×60. The terminal controls the font and must
support Unicode border/chart glyphs. Textual respects `NO_COLOR`; unset it to
see the palettes. Styling is in `termdash/styles.tcss`.

| Key | Action |
| --- | --- |
| `q` | Quit |
| `t` | Cycle dark → light → retro green → dark |
| `r` | Request refresh for every provider |
| `?` | Open or close help |
| `Esc` / `Enter` | Close help |

## Configuration

On first launch termdash writes a commented `config.toml` in your user config
directory: `%APPDATA%/termdash` on Windows, `$XDG_CONFIG_HOME/termdash` (default
`~/.config/termdash`) on Linux, or `~/Library/Application Support/termdash` on macOS.
Use `--config PATH` to select another file. Invalid TOML, unknown keys, and invalid
values produce an error naming the file and setting before the UI starts.

```toml
location = "London"
units = "metric"
theme = "dark"

[refresh]
system = 2
git = 5
weather = 900
demo = 2

[git]
repo = "."
```

`location` is a city name of at least two characters. `units` accepts `metric`
or `imperial`; both weather settings are reserved for the live weather provider.
`theme` selects `dark`, `light`, or `retro` at startup. The `t` key changes the
current session only. Every refresh value must be positive, finite seconds.
`git.repo` accepts a path; `~` expands to your home and relative paths use the
launch directory. Use forward slashes (`C:/src/project`) or TOML literal strings
(`'C:\src\project'`) for Windows paths. Missing keys use the defaults above.

## Providers and panel states

`Provider` is a `typing.Protocol` with `fetch()` returning an immutable
dataclass. Widgets only consume data; fetching runs in independent Textual
thread workers. Results reach the UI through thread-safe messages. Each
provider has one worker, so refreshes cannot overlap that provider's fetches.

- **SystemProvider** (`SystemSnapshot`): psutil per-core CPU measured over a
  0.1-second window, memory percentage/total, usage of the current drive's root
  filesystem, and aggregate network throughput. Bytes/s are counter deltas
  divided by monotonic elapsed seconds. The first rate is zero while establishing
  a baseline; missing/reset counters also restart at zero. The CPU chart shows
  logical cores in live mode; memory retains up to 48 samples. Network bars use
  an adaptive scale, not a measured link capacity. Charts scale to their own range.
- **GitProvider** (`GitData`): runs `git status --porcelain=v2 --branch -z --untracked-files=all`
  and reads the last commit's subject and relative time. Shows branch, ahead/behind,
  staged/unstaged/untracked counts, and up to three file names as space permits.
  A file can count as both staged and unstaged. Detached HEAD includes the short
  commit ID; a new repository shows “No commits yet”. Non-repositories and missing
  directories show a friendly empty state. Each Git command has a five-second
  timeout. Ahead/behind reflect locally known upstream refs; the provider never
  fetches from a remote.
- **DemoProvider** (`Snapshot`): bounded simulated values, including weather.
  Keeps the original `snapshot()` API as an alias for `fetch()`. In demo mode,
  CPU/memory charts show 48 history samples and network bars use a 100 Mb/s scale.

Panel border badges show `LOADING`, `LIVE`, `DEMO`, `STALE` or `ERROR`. A provider
is stale after no successful sample for twice its interval (at least 0.5 seconds).
Slow and failed providers retain the last successful data while the other workers
and keyboard actions continue. Errors retry automatically after the configured
delay. Hover a panel for the error and refresh details; `r` retries sooner.

## Structure

- `termdash/app.py`: composition, provider workers, result messages, badges, help.
- `termdash/__main__.py`: CLI options and interval validation.
- `termdash/config.py`, `paths.py`: validated TOML and per-user directories.
- `termdash/data.py`: immutable panel dataclasses and demo provider.
- `termdash/providers/`: protocol, psutil provider and Git provider.
- `termdash/panels/`: reactive widgets accepting fresh matching data objects.
- `tests/`: pytest provider/CLI tests and Textual Pilot checks.
- `docs/termdash-retro.svg`: example demo screenshot at 80×24.

## Build and test

Install from the checkout with `python -m pip install .`; the `termdash` console
script and `python -m termdash` both start the app. For development, use the
editable install above. On Linux, activate `.venv/bin/activate` and use `python`
and `termdash` without the Windows paths.

Build a wheel and run checks:

```powershell
.\.venv\Scripts\python.exe -m compileall -q termdash tests
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir dist
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Tests use fake psutil readings and `tmp_path` Git repositories for clean, dirty,
ahead/behind, detached, unborn, renamed and conflicted states. Pilot checks cover
themes, help, keyboard refresh/quit, layout, worker thread identity, independent
intervals, blocked providers, stale/error badges, retained data and recovery.
The screenshot test writes to a temporary directory and leaves tracked files
unchanged. No pytest async plugin is required.

GitHub Actions runs ruff, pytest, a wheel build, and an installed console-script
smoke check on Linux and Windows with Python 3.11, 3.12, and 3.13. The wheel
includes the dashboard stylesheet and MIT license.

## What I learned

TODO

## Limits

Weather remains demo data. No theme persistence or layouts below 80×24. Long
Git subjects are truncated to fit (hover for the full subject); the file list is
a preview, while counts include every file. CPU is a short-window measurement,
and network rates aggregate interfaces rather than representing one adapter.
Git status and log are separate reads, so a concurrent commit can briefly mix
samples. Python cannot forcibly cancel an in-flight thread; quit cancels polling
and wakes idle workers, but process exit may wait for an active system call to
return (Git commands are bounded by their timeout).

MIT licensed. Copyright holder: TODO.
