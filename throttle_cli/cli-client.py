from pathlib import Path

from xdg import BaseDirectory

from . import __version__
from .arglib import storeJob, storeSilentJob
from .client import get_info, send_message
from .structures import ActionType


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="throttle", description="send jobs to the throttle server"
    )
    parser.add_argument(
        "--version", action="version", version=f"throttle {__version__}"
    )
    parser.add_argument(
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
        "--statistics",
        action="store_true",
        help="Print statistics for handled commands.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print status information for currently running workers.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "csv", "latex", "html", "json", "markdown", "plain"],
        default="text",
        help="Format for printing results.",
    )
    args, unknownargs = parser.parse_known_args()
    socketpath = Path(BaseDirectory.get_runtime_dir()) / "throttle.sock"
    if args.statistics:
        get_info(socketpath, ActionType.STATS, args.format)
        return
    if args.status:
        get_info(socketpath, ActionType.STATUS, args.format)
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
