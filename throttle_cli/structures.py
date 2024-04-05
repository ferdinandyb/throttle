from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List


class ActionType(Enum):
    RUN = auto()  # run job
    CONT = auto()  # don't run this job, but call next
    KILL = auto()  # kill job
    CLEAN = auto()  # clear up dangling jobs
    STATS = auto()  # return stats to client
    STATUS = auto()  # return current status to client


@dataclass
class Msg:
    action: ActionType
    jobs: List[str] = field(default_factory=list)
    notifications: List[int] = field(default_factory=list)
    index: int = 0
    origin: str = ""

    @property
    def job(self) -> str:
        return self.jobs[self.index]

    @job.setter
    def job(self, j) -> None:
        self.jobs[self.index] = j

    @property
    def notification(self) -> int:
        return self.notifications[self.index]

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
