from .server import start_server
import logging
from pathlib import Path
from .client import send_message
from xdg import BaseDirectory


def main():
    import argparse

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-s", "--server", action="store_true", help="Start server.")
    group.add_argument(
        "-c",
        "--cmd",
        action="append",
        help="Explicitly give cmd to execute, can be given multiple times, in that case, they will be run consecutively.",
    )
    group.add_argument(
        "-k", "--kill", action="store_true", help="Kill a previously started cmd."
    )
    parser.add_argument(
        "--LOGLEVEL",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set loglevel.",
    )
    args, unknownargs = parser.parse_known_args()
    socketpath = Path(BaseDirectory.get_runtime_dir()) / "throttle.sock"
    loglevel = logging.INFO
    if args.LOGLEVEL:
        loglevel = getattr(logging, args.LOGLEVEL)
    if args.server:
        start_server(socketpath, loglevel)
        return

    send_message(socketpath, args.kill, args.cmd, unknownargs)


if __name__ == "__main__":
    main()
