from pathlib import Path
from typing import List

from jsonrpclib import ServerProxy

from .structures import ActionType


def send_message(
    socketpath: Path, kill: bool, cmd: List[str], unknownargs: List[str]
) -> None:
    if not socketpath.exists():
        print("socket doesn't exist, is throttle running?")
        import sys

        sys.exit(1)
    action = ActionType.KILL if kill else ActionType.RUN
    job: List[str] = []
    if cmd is not None:
        job += cmd
    if len(unknownargs) > 0:
        job += [" ".join(unknownargs)]
    if len(job) == 0:
        return
    client = ServerProxy(f"unix+http://{socketpath}")
    client.handle({"action": action, "cmd": job})
    client("close")()
