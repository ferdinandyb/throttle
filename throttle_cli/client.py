from pathlib import Path
from typing import List

from jsonrpclib import ServerProxy

from .statparser import parse_stats
from .structures import ActionType


def send_message(
    socketpath: Path,
    kill: bool,
    jobs: List[str],
    notifications: List[int],
    origin: str,
    unknownargs: List[str],
) -> None:
    if not socketpath.exists():
        print("Socket doesn't exist, is the throttle server running?")
        print("You can start the server by running throttle-server")
        import sys

        sys.exit(1)
    action = ActionType.KILL if kill else ActionType.RUN
    mergedjobs: List[str] = []
    if notifications is None:
        notifications = []
    if jobs is not None:
        mergedjobs += jobs
    if len(unknownargs) > 0:
        mergedjobs += [" ".join(unknownargs)]
        notifications.append(1)
    if len(mergedjobs) == 0:
        return
    try:
        client = ServerProxy(f"unix+http://{socketpath}")
        client.handle(
            {
                "action": action,
                "jobs": mergedjobs,
                "notifications": notifications,
                "origin": origin,
            }
        )
        client("close")()
    except ConnectionRefusedError:
        import sys

        print(
            "Connection refused: did you start the server with `throttle-server`?",
            file=sys.stderr,
        )
        sys.exit(1)


def get_info(socketpath, action, format):
    if not socketpath.exists():
        print("Socket doesn't exist, is the throttle server running?")
        print("You can start the server by running throttle-server")
        import sys

        sys.exit(1)
    try:
        client = ServerProxy(f"unix+http://{socketpath}")
        retval = client.info({"action": action})
        print(parse_stats(retval, format))
        client("close")()
    except ConnectionRefusedError:
        import sys

        print(
            "Connection refused: did you start the server with `throttle-server`?",
            file=sys.stderr,
        )
        sys.exit(1)
