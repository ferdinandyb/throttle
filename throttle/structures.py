from dataclasses import dataclass
from enum import Enum
from typing import List


class ActionType(Enum):
    RUN = 0  # run job
    KILL = 1  # kill job
    CLEAN = 2  # clear up dangling jobs


@dataclass
class Msg:
    cmd: List[str]
    action: ActionType
    index: int = 0

    @property
    def job(self) -> str:
        return self.cmd[self.index]

    def next(self):
        if self.index < len(self.cmd) - 1:
            self.index += 1
            return True
        else:
            return False
