from pathlib import Path
from typing import List

from jsonrpclib import ServerProxy

from .structures import ActionType


def send_message(
    socketpath: Path, kill: bool, jobs: List[str], origin: str, unknownargs: List[str]
) -> None:
    if not socketpath.exists():
        print("socket doesn't exist, is throttle running?")
        import sys

        sys.exit(1)
    action = ActionType.KILL if kill else ActionType.RUN
    mergedjobs: List[str] = []
    if jobs is not None:
        mergedjobs += jobs
    if len(unknownargs) > 0:
        mergedjobs += [" ".join(unknownargs)]
    if len(mergedjobs) == 0:
        return
    try:
        client = ServerProxy(f"unix+http://{socketpath}")
        client.handle({"action": action, "jobs": mergedjobs, "origin": origin})
        client("close")()
    except ConnectionRefusedError:
        import sys

        print(
            "Connection refused: did you start the server with `throttle --server`?",
            file=sys.stderr,
        )
        sys.exit(1)
