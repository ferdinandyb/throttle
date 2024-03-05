import logging
import queue
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from multiprocessing import Event, Process, Queue
from multiprocessing.synchronize import Event as SyncEvent
from pathlib import Path
from typing import Dict, List

import toml
from xdg import BaseDirectory

from .structures import ActionType, Msg


@dataclass
class workeritem:
    p: Process
    q: Queue
    e: SyncEvent
    t: float


class CommandWorker:
    def __init__(self, queue: Queue, logqueue: Queue):
        self.q = queue
        self.logqueue = logqueue
        self.logger = logging.getLogger("msg_worker")
        self.data: Dict[str, workeritem] = {}
        self.timeout = 30
        self.filters: List[Dict[str, str]] = []
        self.notification_cmd = None
        self.notify_on_counter = 0
        self.job_timeout = 60 * 60
        self.retry_sequence = [5, 15, 30, 60, 120, 300, 900]

        self.loadConfig()

    def loadConfig(self):
        configdir = BaseDirectory.load_first_config("throttle")
        if configdir is None:
            return
        configpath = Path(configdir) / "config.toml"
        if not configpath.exists():
            return

        # let's fail if the config is messed up
        config = toml.load(Path(configdir) / "config.toml")
        if "task_timeout" in config:
            self.timeout = config["task_timeout"]
        if "filters" in config:
            for f in config["filters"]:
                if "pattern" not in f or "substitute" not in f:
                    self.logger.error(f"{f} is not a valid filter config")
            self.filters = config["filters"]
        if "retry_sequence" in config:
            self.retry_sequence = config["retry_sequence"]
        if "notification_cmd" in config:
            self.notification_cmd = config["notification_cmd"]
        if "notify_on_counter" in config:
            self.notify_on_counter = config["notify_on_counter"]
        if "job_timeout" in config:
            self.job_timeout = config["job_timeout"]

    def checkregex(self, msg: Msg) -> Msg:
        self.logger.debug(f"checking: {self.filters}")
        for i, job in enumerate(msg.cmd):
            for item in self.filters:
                self.logger.debug(
                    f"pattern: {item['pattern']}, subsitute: {item['substitute']}, input: {job}"
                )
                newjob = re.sub(item["pattern"], item["substitute"], job)
                if newjob != job:
                    self.logger.info(f"regex rewrite {job} -> {newjob}")
                    msg.cmd[i] = newjob
                    break
        self.logger.debug(f"regexed: {msg}")
        return msg

    def handleRun(self, msg) -> None:
        msg = self.checkregex(msg)
        if msg.job not in self.data or not self.data[msg.job].p.is_alive():
            self.logger.debug(f"{msg.job}: doesn't exist or finished, creating")
            q: Queue[Msg] = Queue()
            e = Event()
            p = Process(
                target=self.runworkerFactory(),
                args=(q, e, self.timeout, msg.job),
            )
            p.start()
            self.data[msg.job] = workeritem(p, q, e, time.time())
        self.logger.debug(
            f"{msg.job}: approx queue size {self.data[msg.job].q.qsize()}"
        )
        if self.data[msg.job].q.empty():
            self.logger.debug(f"{msg.job}: empty, adding new")
            self.data[msg.job].q.put(msg)
        self.data[msg.job].t = time.time()

    def handleKill(self, msg) -> None:
        for job in msg.cmd:
            if job in self.data:
                self.data[job].e.set()
        self.logger.debug(f"remaining jobs: {self.data.keys()}")

    def msgworker(self) -> None:
        """
        Handle client inputs from the queue.
        """

        while True:
            msg: Msg = self.q.get()
            self.logger.info(f"handling {msg}")
            if msg.action == ActionType.RUN:
                self.handleRun(msg)
            if msg.action == ActionType.CLEAN:
                self.cleanup()
            if msg.action == ActionType.KILL:
                self.handleKill(msg)

    def sendNotification(
        self,
        job: str = "",
        urgency: str = "critical",
        errcode: int = -1000,
        msg: str = "",
    ) -> None:
        if self.notification_cmd is None:
            return
        try:
            self.logger.debug(f"sending message {job=}, {msg=}, {urgency=}, {errcode=}")
            subprocess.run(
                shlex.split(
                    self.notification_cmd.format(
                        job=job,
                        urgency=urgency,
                        msg=msg,
                        errcode=errcode,
                    )
                )
            )
        except Exception as e:
            self.logger.error(f"failed sending notification command with error: {e}")

    def runworkerFactory(self):
        """
        Factory for handling each type of jobs.
        """

        def handlejobs(msg: Msg, e, logger) -> None:
            retry_timeout_index = -1
            error_counter = 0
            while True:
                if e.is_set():
                    break
                if retry_timeout_index + 1 < len(self.retry_sequence):
                    retry_timeout_index += 1
                success = True
                logger.debug(msg)
                logger.debug(f"running job: {msg.job} with timeout {self.job_timeout}")
                try:
                    proc = subprocess.run(
                        shlex.split(msg.job),
                        capture_output=True,
                        timeout=self.job_timeout,
                    )
                    if proc.returncode != 0:
                        success = False
                        error_counter += 1
                        logger.error(
                            f"{proc.returncode=}, {proc.stdout=}, {proc.stderr=}, {error_counter=}"
                        )
                        if error_counter >= self.notify_on_counter:
                            self.sendNotification(
                                job=msg.job,
                                msg=f"c:{error_counter}|{proc.stderr.decode('utf-8')} - {proc.stdout.decode('utf-8')}",
                                errcode=proc.returncode,
                            )
                            error_counter = 0
                except Exception as error:
                    success = False
                    error_counter += 1
                    logger.error(f"{msg.job}'s subprocess failed with {error}")
                    if error_counter >= self.notify_on_counter:
                        self.sendNotification(
                            job=msg.job,
                            msg=f"subprocess failed with {error}",
                        )
                        error_counter = 0

                if success:
                    break
                if e.is_set():
                    break
                time.sleep(self.retry_sequence[retry_timeout_index])

        def worker(q, e, timeout, name) -> None:
            self.retry_sequence

            logger = logging.getLogger(f"{name.replace(' ','_')}_worker")
            counter = 0
            logger.info("starting process")

            while True:
                if e.is_set():
                    break
                try:
                    msg = q.get(timeout=timeout)
                    counter += 1
                    logger.info(f"start run no: {counter}")
                    handlejobs(msg, e, logger)
                    logger.info(f"finish run no: {counter}")
                    if msg.next():
                        self.q.put(msg)
                except queue.Empty:
                    logger.info("closing process")
                    break
            self.q.put(Msg(cmd=[], action=ActionType.CLEAN))

        return worker

    def cleanup(self):
        self.logger.debug(f"cleanup underway, {self.data.keys()}")
        toclean = []
        for key, val in self.data.items():
            if not val.p.is_alive():
                toclean.append(key)

        for key in toclean:
            del self.data[key]
        self.logger.debug(f"cleanup finished, {self.data.keys()}")
