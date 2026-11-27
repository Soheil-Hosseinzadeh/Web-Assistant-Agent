"""Onnie - web assistant agent.

Usage:
    python main.py              # web GUI (default)
    python main.py -m cli       # terminal interface
"""

import argparse
import sys


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Onnie - web assistant agent")
    parser.add_argument(
        "-m",
        "--mode",
        type=str.lower,
        choices=["visual", "cli"],
        default="visual",
        help="visual = web GUI (default), cli = terminal interface",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # Load the configuration and prepare the environment BEFORE smolagents /
    # litellm are imported (they read proxy settings at import time).
    from onnie.config import ConfigError, apply_environment, get_settings

    try:
        apply_environment(get_settings())
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")

    # NiceGUI is only imported in visual mode; rich only in CLI mode.
    if args.mode == "cli":
        from onnie.cli import run_cli

        run_cli()
    else:
        from onnie.gui import run_gui

        run_gui()


if __name__ in {"__main__", "__mp_main__"}:
    main()
