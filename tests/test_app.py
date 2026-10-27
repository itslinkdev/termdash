from pathlib import Path
import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from xml.etree import ElementTree

from textual.widgets import ProgressBar, Sparkline, Static

from termdash.app import HelpScreen, TermdashApp
from termdash.data import DemoProvider, GitData
from termdash.panels.git import GitPanel
from termdash.panels.io import IOPanel
from termdash.panels.system import SystemPanel
from termdash.panels.weather import WeatherPanel


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        # CI may disable color; the screenshot must exercise the actual palettes.
        os.environ.pop("NO_COLOR", None)

    async def test_demo_themes_and_svg(self) -> None:
        app = TermdashApp(DemoProvider(seed=7))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            self.assertEqual(app.theme_name, "dark")
            await pilot.press("t")
            self.assertEqual(app.theme_name, "light")
            self.assertTrue(app.screen.has_class("light"))
            self.assertEqual(app.screen.styles.background.hex.lower(), "#e8ebed")
            await pilot.press("t")
            self.assertEqual(app.theme_name, "retro")
            self.assertTrue(app.screen.has_class("retro"))
            directory = TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            path = app.save_screenshot("termdash-retro.svg", path=directory.name)
            screenshot = Path(path)
            svg = screenshot.read_text(encoding="utf-8")
            # Rich exports a whitespace-only line; keep generated diffs clean.
            screenshot.write_text("\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
                                  encoding="utf-8")
            self.assertTrue(ElementTree.parse(path).getroot().tag.endswith("svg"))
            self.assertIn("#98ff98", svg)
            await pilot.press("t")
            self.assertEqual(app.theme_name, "dark")
            await pilot.press("q")
        self.assertFalse(app.is_running)

    async def test_layout_refresh_help_and_reactive_updates(self) -> None:
        app = TermdashApp(DemoProvider(seed=9))
        async with app.run_test(size=(80, 24)) as pilot:
            for width, height in ((80, 24), (120, 36), (200, 60)):
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                panels = [app.query_one(panel) for panel in
                          (SystemPanel, WeatherPanel, GitPanel, IOPanel)]
                self.assertEqual(panels[0].region.y, panels[1].region.y)
                self.assertEqual(panels[0].region.x, panels[2].region.x)
                self.assertLess(panels[0].region.right, panels[1].region.x)
                self.assertLess(panels[0].region.bottom, panels[2].region.y)
                for panel in panels:
                    self.assertGreater(panel.content_region.width, 30)
                    for widget in panel.query("Static, Sparkline, ProgressBar"):
                        self.assertTrue(panel.content_region.contains_region(widget.region),
                                        f"{widget.id} clipped at {width}x{height}")
                self.assertLessEqual(app.query_one("#footer").region.bottom, height)
            before = app.query_one(SystemPanel).data
            await pilot.press("r")
            self.assertNotEqual(app.query_one(SystemPanel).data, before)
            self.assertEqual(tuple(app.query_one("#cpu-spark", Sparkline).data),
                             app.query_one(SystemPanel).data.cpu)
            data = app.query_one(IOPanel).data
            self.assertEqual(app.query_one("#download-bar", ProgressBar).progress,
                             data.download_mbps)
            app.query_one(GitPanel).data = GitData()
            await pilot.pause()
            self.assertEqual(str(app.query_one("#git-files", Static).content),
                             "Working tree clean")
            await pilot.resize_terminal(80, 24)
            await pilot.press("?")
            self.assertIsInstance(app.screen, HelpScreen)
            help_box = app.screen.query_one("#help-box")
            self.assertTrue(app.screen.region.contains_region(help_box.region))
            await pilot.press("t", "r")
            await pilot.pause(2.1)
            self.assertTrue(app.screen.has_class("light"))
            await pilot.press("escape")
            self.assertNotIsInstance(app.screen, HelpScreen)
            self.assertTrue(app.screen.has_class("light"))


class DemoTests(unittest.TestCase):
    def test_samples_stay_plausible(self) -> None:
        provider = DemoProvider(seed=3)
        previous = provider.snapshot()
        for _ in range(100):
            sample = provider.snapshot()
            self.assertEqual(sample.system.cpu[:-1], previous.system.cpu[1:])
            self.assertEqual(len(sample.system.memory), 48)
            self.assertTrue(all(0 <= value <= 100 for value in sample.system.cpu))
            self.assertTrue(all(0 <= value <= 100 for value in sample.system.memory))
            self.assertLessEqual(sample.io.download_mbps, sample.io.capacity_mbps)
            self.assertLessEqual(sample.io.upload_mbps, sample.io.capacity_mbps)
            self.assertLessEqual(sample.io.disk_used_gib, sample.io.disk_total_gib)
            self.assertTrue(0 <= sample.weather.humidity_percent <= 100)
            previous = sample


if __name__ == "__main__":
    unittest.main()
