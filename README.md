# termdash

A terminal dashboard for Python 3.11+ and Textual. Live mode reads local CPU,
memory, disk, network and Git data, plus current weather from Open-Meteo.
`--demo` keeps all readings simulated and makes no weather requests.
Providers never change your Git repository. No weather API key is needed.

GIF preview: TODO (record a short terminal session).

## Install and run

From this folder, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\termdash.exe
```

On Linux/macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
termdash
```

For a regular install from this checkout, use `python -m pip install .` instead.
Python 3.11+ is required for the standard library's `tomllib`.

Git must be installed and available on PATH. Choose a repository and polling
delays (positive, finite seconds):

```powershell
.\.venv\Scripts\python.exe -m termdash --repo "D:\path\to\repo" --system-interval 1 --git-interval 5
.\.venv\Scripts\python.exe -m termdash --demo --demo-interval 2
.\.venv\Scripts\python.exe -m termdash --help
```

CLI flags override the TOML settings. `git.repo` defaults to the current working
directory. Defaults are 2 seconds for
system data, 5 seconds for Git, 900 seconds for weather, and 2 seconds for demo data. Each delay
starts after that provider's fetch finishes. Pressing `r` wakes waiting workers;
an in-flight fetch finishes before the next fetch starts. Weather refreshes,
including `r` and `--weather-interval`, respect the 15-minute cache TTL.

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

| Setting | Default | Accepted values / meaning |
| --- | --- | --- |
| `location` | `"London"` | City name, at least two characters; first geocoding match wins |
| `units` | `"metric"` | Weather display: `metric` (°C, km/h) or `imperial` (°F, mph) |
| `theme` | `"dark"` | Initial palette: `dark`, `light`, or `retro` |
| `refresh.system` | `2` | System polling delay in seconds |
| `refresh.git` | `5` | Git polling delay in seconds |
| `refresh.weather` | `900` | Weather polling delay; cached answers have a 900-second TTL |
| `refresh.demo` | `2` | Demo polling delay in seconds |
| `git.repo` | `"."` | Git path; relative to the launch directory, `~` expands to home |

Every refresh value must be positive and finite. Missing keys use the defaults
above. The `t` key changes the current session only. Settings are read at startup;
restart after editing. Units apply to weather; system I/O keeps its existing units.
Use forward slashes (`C:/src/project`) or TOML literal strings
(`'C:\src\project'`) for Windows paths. A missing Git directory shows an empty state.

## Providers and panel states

`Provider` and `AsyncProvider` are `typing.Protocol` contracts with `fetch()`
returning an immutable dataclass. Widgets only consume data. System, Git, and
demo fetching runs in independent Textual thread workers; weather uses an async
worker with `httpx.AsyncClient`. Results reach the UI through messages. Each
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
- **WeatherProvider** (`WeatherData`): resolves the configured city with the
  [Open-Meteo geocoding API](https://open-meteo.com/en/docs/geocoding-api), then
  requests temperature, relative humidity, wind speed, and a condition code from
  the [forecast API](https://open-meteo.com/en/docs). The panel shows current
  model conditions, not a multi-day outlook. HTTP requests use a five-second
  timeout per operation. A failed geocoding/forecast sequence gets two retries,
  with delays of 0.5 and 1 second. Invalid or missing response values count as failures.

Weather's last good answer is written atomically as JSON in the user cache directory:
`%LOCALAPPDATA%/termdash` on Windows, `$XDG_CACHE_HOME/termdash` (default
`~/.cache/termdash`) on Linux, or `~/Library/Caches/termdash` on macOS. Cache files
are separated by city. Entries younger than 15 minutes are reused across launches.
After expiry, failed requests show the cached answer with a `STALE` badge and the
failure in its tooltip; stale entries have no maximum fallback age. A failure never
replaces the last good file. Corrupt or future-dated cache entries are ignored.
If the cache directory is unwritable, live readings still work and the last good
answer is retained in memory for that session.

Panel border badges show `LOADING`, `LIVE`, `DEMO`, `STALE` or `ERROR`. A provider
is stale after no successful sample for twice its interval (at least 0.5 seconds).
Weather cached after a failed request is always `STALE`. Without a usable cache,
weather shows `ERROR` and empty readings until recovery.
Slow and failed providers retain the last successful data while the other workers
and keyboard actions continue. Errors retry automatically after the configured
delay. Hover a panel for the error and refresh details; `r` retries sooner.

## Structure

```text
user config.toml -- tomllib + validation -- CLI overrides
                                              |
                                              v
                                        TermdashApp
                                              |
   +----------------------+-------------------+-------------------+
   |                      |                   |                   |
SystemProvider        GitProvider       WeatherProvider      DemoProvider
   | psutil               | git               | async httpx       | --demo
   |                      |              geocoding -> forecast    |
   |                      |                   | <-> JSON cache    |
   +----------------------+-------------------+-------------------+
                                              |
                                   immutable data + messages
                                              |
                              reactive panels + status badges
```

- `termdash/app.py`: composition, provider workers, result messages, badges, help.
- `termdash/__main__.py`: CLI options and interval validation.
- `termdash/config.py`, `paths.py`: validated TOML and per-user directories.
- `termdash/data.py`: immutable panel dataclasses and demo provider.
- `termdash/providers/`: protocols, system, Git and async weather providers.
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

Tests block real HTTP and use `httpx.MockTransport` only inside tests. They check
weather requests, timeout settings, retry backoff, cache TTL, stale fallback,
corrupt cache, offline startup, and recovery. Config tests use temporary files.
Tests also use fake psutil readings and `tmp_path` Git repositories for clean, dirty,
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

City selection uses the first geocoding match; ambiguous city names can select
the wrong place. Weather requires connectivity for an initial successful fetch,
and stale fallback can be arbitrarily old. No layouts below 80×24. Long
Git subjects are truncated to fit (hover for the full subject); the file list is
a preview, while counts include every file. CPU is a short-window measurement,
and network rates aggregate interfaces rather than representing one adapter.
Git status and log are separate reads, so a concurrent commit can briefly mix
samples. Python cannot forcibly cancel an in-flight thread; quit cancels polling
and wakes idle workers, but process exit may wait for an active system call to
return (Git commands are bounded by their timeout).

MIT licensed; see [LICENSE](LICENSE). Copyright holder: TODO.
