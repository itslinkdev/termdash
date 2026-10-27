import argparse
from math import isfinite
from pathlib import Path

from termdash.app import TermdashApp
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
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Git repository (default: cwd)")
    parser.add_argument("--system-interval", type=positive_seconds, default=2,
                        metavar="SECONDS", help="system polling delay (default: 2)")
    parser.add_argument("--git-interval", type=positive_seconds, default=5,
                        metavar="SECONDS", help="Git polling delay (default: 5)")
    parser.add_argument("--demo-interval", type=positive_seconds, default=2,
                        metavar="SECONDS", help="demo/weather polling delay (default: 2)")
    args = parser.parse_args()
    TermdashApp(
        DemoProvider() if args.demo else None, repo=args.repo,
        system_interval=args.system_interval, git_interval=args.git_interval,
        demo_interval=args.demo_interval,
    ).run()


if __name__ == "__main__":
    main()
