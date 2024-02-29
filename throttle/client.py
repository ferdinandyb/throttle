from jsonrpclib import ServerProxy
from typing import List
from pathlib import Path
from .structures import Msg, ActionType
import shlex


def generateKey(cmd: List[List[str]]) -> str:
    return shlex.join([shlex.join(c) for c in cmd])


def send_message(
    socketpath: Path, kill: bool, cmd: List[str], unknownargs: List[str]
) -> None:
    action = ActionType.KILL if kill else ActionType.RUN
    job: List[List[str]] = []
    if cmd is not None:
        job += [shlex.split(c) for c in cmd]
    if len(unknownargs) > 0:
        job += [unknownargs]
    client = ServerProxy(f"unix+http://{socketpath}")
    client.handle({"key": generateKey(job), "action": action, "cmd": job})
    client("close")()
