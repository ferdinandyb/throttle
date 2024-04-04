import logging
from pathlib import Path

from xdg import BaseDirectory

from .client import send_message
from .server import start_server
from .arglib import storeJob, storeSilentJob


def main():
    import argparse

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-s", "--server", action="store_true", help="Start server.")
    group.add_argument(
        "-j",
        "--job",
        action=storeJob,
        help="Explicitly give job to execute, can be given multiple times, in that case, they will be run consecutively.",
    )
    parser.add_argument(
        "-J",
        "--silent-job",
        action=storeSilentJob,
        help="Same as --job, but no notifications will be sent on failure.",
    )
    parser.add_argument(
        "-k", "--kill", action="store_true", help="Kill a previously started job."
    )
    parser.add_argument(
        "-o",
        "--origin",
        type=str,
        help="Set the origin of the message, which might be useful in tracking logs.",
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
    if hasattr(args, "notifications"):
        notifications = args.notifications
    else:
        notifications = []
    send_message(
        socketpath, args.kill, args.job, notifications, args.origin, unknownargs
    )


if __name__ == "__main__":
    main()
