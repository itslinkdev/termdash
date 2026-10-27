import asyncio
from threading import Event, get_ident
import unittest

import pytest
from textual.widgets import Sparkline, Static
from textual.events import Key

from termdash.app import HelpScreen, TermdashApp
from termdash.data import GitData, IOData, SystemData, SystemSnapshot, WeatherData


async def wait_until(predicate, timeout=3):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)


class FakeSystem:
    def __init__(self):
        self.calls = 0
        self.threads = set()
        self.fail = False

    def fetch(self):
        self.calls += 1
        self.threads.add(get_ident())
        if self.fail:
            raise OSError("system temporarily unavailable")
        return SystemSnapshot(
            SystemData((float(self.calls),), (25.0,), 8.0, (20.0, 60.0)),
            IOData(disk_used_gib=40, disk_total_gib=100,
                   download_bytes_per_second=2048, upload_bytes_per_second=512),
        )


class FakeGit:
    def __init__(self):
        self.calls = 0
        self.threads = set()
        self.gate = Event()
        self.gate.set()
        self.started = Event()
        self.fail = False
        self.active = self.max_active = 0

    def fetch(self):
        self.calls += 1
        self.threads.add(get_ident())
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.started.set()
        try:
            if not self.gate.wait(10):
                raise TimeoutError("test provider was not released")
            if self.fail:
                raise OSError("Git temporarily unavailable [retry]")
            return GitData(branch="main", last_commit_subject="Keep [brackets] literal",
                           last_commit_relative_time="2 minutes ago")
        finally:
            self.active -= 1


class FakeWeather:
    def __init__(self):
        self.calls = self.active = self.max_active = 0
        self.stale = self.fail = False
        self.gate = asyncio.Event()
        self.gate.set()

    async def fetch(self):
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await self.gate.wait()
            if self.fail:
                raise OSError("Weather unavailable")
            return WeatherData(20, "Clear sky", 50, 10, "Test [city]", stale=self.stale,
                               error="offline" if self.stale else "")
        finally:
            self.active -= 1


@pytest.fixture(autouse=True)
def offline_weather(monkeypatch):
    monkeypatch.setattr("termdash.app.WeatherProvider", lambda location: FakeWeather())


class PollingTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_weather_stale_error_units_and_recovery(self):
        weather = FakeWeather()
        app = TermdashApp(system_provider=FakeSystem(), git_provider=FakeGit(),
                          weather_provider=weather, weather_interval=60,
                          theme="light", units="imperial")
        async with app.run_test(size=(80, 24)):
            await wait_until(lambda: app.polls["weather"].last_success is not None)
            self.assertTrue(app.screen.has_class("light"))
            self.assertEqual(str(app.panels["weather"].border_subtitle), "[LIVE]")
            self.assertEqual(str(app.query_one("#weather-temperature", Static).content), "68.0 °F")
            self.assertEqual(str(app.query_one("#weather-wind", Static).content), "Wind       6 mph")
            self.assertEqual(str(app.query_one("#weather-location", Static).content), "Test [city]")
            weather.stale = True
            app.action_refresh_data()
            await wait_until(lambda: str(app.panels["weather"].border_subtitle) == "[STALE]")
            self.assertIn("offline", str(app.panels["weather"].tooltip))
            self.assertEqual(app.panels["weather"].data.temperature_c, 20)
            weather.stale = False
            app.action_refresh_data()
            await wait_until(lambda: str(app.panels["weather"].border_subtitle) == "[LIVE]")
            weather.fail = True
            previous = app.panels["weather"].data
            app.action_refresh_data()
            await wait_until(lambda: str(app.panels["weather"].border_subtitle) == "[ERROR]")
            self.assertEqual(app.panels["weather"].data, previous)

    async def test_pending_weather_keeps_ui_responsive_and_cancels_on_quit(self):
        weather, system = FakeWeather(), FakeSystem()
        weather.gate.clear()
        app = TermdashApp(system_provider=system, git_provider=FakeGit(),
                          weather_provider=weather, system_interval=0.05, weather_interval=60)
        async with app.run_test(size=(80, 24)):
            await wait_until(lambda: weather.active == 1 and system.calls > 1)
            self.assertEqual(str(app.query_one("#weather-temperature", Static).content), "--")
            app.action_refresh_data()
            app.action_refresh_data()
            app.post_message(Key("t", "t"))
            await wait_until(lambda: app.theme_name == "light")
            self.assertEqual(weather.max_active, 1)
            app.post_message(Key("q", "q"))
            await wait_until(lambda: not app.is_running)
        await wait_until(lambda: weather.active == 0)
        self.assertTrue(app.polls["weather"].worker.is_cancelled)

    async def test_slow_git_keeps_ui_and_other_providers_responsive(self):
        system, git = FakeSystem(), FakeGit()
        app = TermdashApp(system_provider=system, git_provider=git,
                          system_interval=0.05, git_interval=0.05)
        try:
            async with app.run_test(size=(80, 24)):
                await wait_until(lambda: app.polls["git"].last_success is not None)
                previous = app.panels["git"].data
                git.gate.clear()
                git.started.clear()
                app.action_refresh_data()
                await wait_until(git.started.is_set)
                before = system.calls
                await wait_until(lambda: str(app.panels["git"].border_subtitle) == "[STALE]")
                self.assertGreater(system.calls, before)
                self.assertEqual(app.panels["git"].data, previous)
                # Pilot.press waits for CPU idleness, which frequent polling need not allow.
                app.post_message(Key("t", "t"))
                await wait_until(lambda: app.theme_name == "light", timeout=2)
                app.post_message(Key("question_mark", "?"))
                await wait_until(lambda: isinstance(app.screen, HelpScreen), timeout=2)
                app.post_message(Key("r", "r"))
                app.post_message(Key("r", "r"))
                self.assertEqual(app.theme_name, "light")
                self.assertIsInstance(app.screen, HelpScreen)
                await asyncio.sleep(1.1)  # The clock and workers also run under the modal.
                self.assertEqual(git.max_active, 1)
                self.assertNotIn(get_ident(), system.threads | git.threads)
                self.assertEqual(tuple(app.panels["system"].query_one("#cpu-spark", Sparkline).data),
                                 (20.0, 60.0))
                self.assertIn("2048 B/s", str(app.panels["io"].query_one("#download-label", Static).content))
                app.post_message(Key("q", "q"))
                await wait_until(lambda: not app.is_running, timeout=2)
            self.assertFalse(app.is_running)
        finally:
            git.gate.set()
        await wait_until(lambda: git.active == 0)

    async def test_errors_keep_data_and_recover_automatically(self):
        system, git = FakeSystem(), FakeGit()
        app = TermdashApp(system_provider=system, git_provider=git,
                          system_interval=0.05, git_interval=0.03)
        async with app.run_test():
            await wait_until(lambda: all(p.last_success is not None for p in app.polls.values()))
            git.fail = system.fail = True
            await wait_until(lambda: app.polls["git"].error and app.polls["system"].error)
            previous_git = app.panels["git"].data
            previous_system = app.panels["system"].data
            previous_io = app.panels["io"].data
            failed_git, failed_system = git.calls, system.calls
            await wait_until(lambda: git.calls > failed_git + 1 and system.calls > failed_system + 1)
            for name in ("git", "system", "io"):
                self.assertEqual(str(app.panels[name].border_subtitle), "[ERROR]")
            self.assertEqual(app.panels["git"].data, previous_git)
            self.assertEqual(app.panels["system"].data, previous_system)
            self.assertEqual(app.panels["io"].data, previous_io)
            self.assertIn("retry", str(app.panels["git"].tooltip))
            failed_calls = git.calls
            await wait_until(lambda: git.calls > failed_calls)
            git.fail = system.fail = False
            await wait_until(lambda: not app.polls["git"].error and not app.polls["system"].error)
            self.assertEqual(str(app.panels["git"].border_subtitle), "[LIVE]")
            self.assertEqual(str(app.panels["weather"].border_subtitle), "[LIVE]")
            self.assertEqual(str(app.panels["git"].query_one("#git-commit", Static).content),
                             "Keep [brackets] literal")

    async def test_intervals_manual_refresh_and_idle_worker_shutdown(self):
        system, git = FakeSystem(), FakeGit()
        app = TermdashApp(system_provider=system, git_provider=git,
                          system_interval=0.03, git_interval=60, demo_interval=60)
        async with app.run_test() as pilot:
            await wait_until(lambda: app.polls["git"].last_success is not None)
            await wait_until(lambda: system.calls >= 3)
            self.assertEqual(git.calls, 1)
            self.assertEqual(str(app.panels["git"].border_subtitle), "[LIVE]")
            await pilot.press("r")
            await wait_until(lambda: git.calls == 2)
            await asyncio.wait_for(pilot.press("q"), 2)
        self.assertTrue(all(p.worker.is_cancelled for p in app.polls.values()))


def test_non_repo_empty_state_and_live_layout(tmp_path):
    async def scenario():
        app = TermdashApp(repo=tmp_path, system_provider=FakeSystem())
        async with app.run_test(size=(80, 24)) as pilot:
            await wait_until(lambda: app.polls["git"].last_success is not None)
            await pilot.pause()
            assert not app.panels["git"].data.is_repo
            assert str(app.panels["git"].query_one("#git-branch", Static).content) == "Not a Git repository"
            assert "--repo" in str(app.panels["git"].query_one("#git-sync", Static).content)
            for panel in app.panels.values():
                for widget in panel.query("Static, Sparkline, ProgressBar"):
                    assert panel.content_region.contains_region(widget.region), widget.id

    asyncio.run(scenario())
