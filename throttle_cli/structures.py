from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class ActionType(Enum):
    RUN = auto()  # run job
    CONT = auto()  # don't run this job, but call next
    KILL = auto()  # kill job
    CLEAN = auto()  # clear up dangling jobs


@dataclass
class Msg:
    jobs: List[str]
    action: ActionType
    index: int = 0
    origin: str = ""

    @property
    def job(self) -> str:
        return self.jobs[self.index]

    @job.setter
    def job(self, j) -> None:
        self.jobs[self.index] = j

    def next(self):
        """
        Set the next job as executable.
        """

        if self.index < len(self.jobs) - 1:
            self.action = ActionType.RUN
            self.index += 1
            return True
        return False

    def cont(self) -> bool:
        """
        If there is a next job, set the current job as skippable.
        """
        if self.index < len(self.jobs) - 1:
            self.action = ActionType.CONT
            return True
        return False
