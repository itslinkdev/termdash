import argparse

from termdash.app import TermdashApp


def main() -> None:
    parser = argparse.ArgumentParser(description="termdash visual dashboard")
    parser.add_argument("--demo", action="store_true", help="use simulated data")
    args = parser.parse_args()
    if not args.demo:
        parser.error("only demo mode is available; pass --demo")
    TermdashApp().run()


if __name__ == "__main__":
    main()
