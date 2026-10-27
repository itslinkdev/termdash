from pathlib import Path
from unittest.mock import Mock

import pytest

from termdash import __main__ as cli
from termdash.app import TermdashApp
from termdash.data import DemoProvider


def test_cli_defaults_to_live_cwd(monkeypatch, tmp_path):
    app = Mock()
    constructor = Mock(return_value=app)
    monkeypatch.setattr(cli, "TermdashApp", constructor)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["termdash"])
    cli.main()
    constructor.assert_called_once_with(None, repo=tmp_path, system_interval=2,
                                        git_interval=5, demo_interval=2)
    app.run.assert_called_once_with()


def test_cli_demo_repo_and_provider_intervals(monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(cli, "TermdashApp", constructor)
    monkeypatch.setattr("sys.argv", ["termdash", "--demo", "--repo", "some repo",
                                    "--system-interval", "1.5", "--git-interval", "4",
                                    "--demo-interval", "0.25"])
    cli.main()
    args, kwargs = constructor.call_args
    assert isinstance(args[0], DemoProvider)
    assert kwargs == dict(repo=Path("some repo"), system_interval=1.5,
                          git_interval=4.0, demo_interval=0.25)


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "-inf", "nope"])
def test_cli_rejects_invalid_intervals(monkeypatch, value):
    monkeypatch.setattr("sys.argv", ["termdash", f"--git-interval={value}"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


@pytest.mark.parametrize("name", ["system_interval", "git_interval", "demo_interval"])
def test_app_also_validates_intervals(name):
    with pytest.raises(ValueError, match="positive, finite"):
        TermdashApp(**{name: float("nan")})
