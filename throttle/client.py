import shlex
from pathlib import Path
from typing import List

from jsonrpclib import ServerProxy

from .structures import ActionType


def generateKey(cmd: List[List[str]]) -> str:
    return shlex.join([shlex.join(c) for c in cmd])


def send_message(
    socketpath: Path, kill: bool, cmd: List[str], unknownargs: List[str]
) -> None:
    if not socketpath.exists():
        print("socket doesn't exist, is throttle running?")
        import sys

        sys.exit(1)
    action = ActionType.KILL if kill else ActionType.RUN
    job: List[List[str]] = []
    if cmd is not None:
        job += [shlex.split(c) for c in cmd]
    if len(unknownargs) > 0:
        job += [unknownargs]
    client = ServerProxy(f"unix+http://{socketpath}")
    client.handle({"key": generateKey(job), "action": action, "cmd": job})
    client("close")()
