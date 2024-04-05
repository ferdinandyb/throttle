import logging
from pathlib import Path

from xdg import BaseDirectory

from . import __version__
from .server import start_server


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="throttle-server", description="start the throttle server"
    )
    parser.add_argument(
        "--LOGLEVEL",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set loglevel.",
    )
    parser.add_argument(
        "--version", action="version", version=f"throttle {__version__}"
    )
    args = parser.parse_args()
    socketpath = Path(BaseDirectory.get_runtime_dir()) / "throttle.sock"
    loglevel = logging.INFO
    if args.LOGLEVEL:
        loglevel = getattr(logging, args.LOGLEVEL)
    start_server(socketpath, loglevel)


if __name__ == "__main__":
    main()
