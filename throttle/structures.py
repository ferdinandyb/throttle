from dataclasses import dataclass
from typing import List
from enum import Enum


class ActionType(Enum):
    RUN = 0  # run job
    KILL = 1  # kill job
    CLEAN = 2  # clear up dangling jobs


@dataclass
class Msg:
    key: str
    action: ActionType
    cmd: List[List[str]]
