from dataclasses import dataclass
from enum import Enum
from typing import List


class ActionType(Enum):
    RUN = 0  # run job
    KILL = 1  # kill job
    CLEAN = 2  # clear up dangling jobs


@dataclass
class Msg:
    key: str
    cmd: List[str]
    action: ActionType
