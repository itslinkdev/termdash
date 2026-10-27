import argparse
from math import isfinite
from pathlib import Path

from termdash.app import TermdashApp
from termdash.config import ConfigError, load_config
from termdash.data import DemoProvider


def positive_seconds(value: str) -> float:
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("use positive, finite seconds") from None
    if not isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("use positive, finite seconds")
    return seconds


def main() -> None:
    parser = argparse.ArgumentParser(description="termdash local system and Git dashboard")
    parser.add_argument("--demo", action="store_true", help="use simulated data")
    parser.add_argument("--config", type=Path, help="TOML file (default: user config directory)")
    parser.add_argument("--repo", type=Path, help="override configured Git repository")
    parser.add_argument("--system-interval", type=positive_seconds,
                        metavar="SECONDS", help="override system polling delay")
    parser.add_argument("--git-interval", type=positive_seconds,
                        metavar="SECONDS", help="override Git polling delay")
    parser.add_argument("--demo-interval", type=positive_seconds,
                        metavar="SECONDS", help="override demo polling delay")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        parser.error(str(exc))
    TermdashApp(
        DemoProvider() if args.demo else None, repo=args.repo or config.repo,
        system_interval=args.system_interval or config.system_interval,
        git_interval=args.git_interval or config.git_interval,
        demo_interval=args.demo_interval or config.demo_interval,
        theme=config.theme,
    ).run()


if __name__ == "__main__":
    main()
