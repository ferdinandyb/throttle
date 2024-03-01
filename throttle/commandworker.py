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
        self.job_timeout = 600
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
        print("config", config)
        if "task_timeout" in config:
            self.timeout = config["task_timeout"]
        if "filters" in config:
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
                if re.search(item["regex"], shlex.join(job)):
                    self.logger.info(f"regex rewrite {job} -> {item['result']}")
                    msg.cmd[i] = shlex.split(item["result"])
                    break
        self.logger.debug(f"regexed: {msg}")
        return msg

    def handleRun(self, msg) -> None:
        msg = self.checkregex(msg)
        if msg.key not in self.data or not self.data[msg.key].p.is_alive():
            self.logger.debug(f"{msg.key}: doesn't exist or finished, creating")
            q: Queue[Msg] = Queue()
            e = Event()
            p = Process(
                target=self.runworkerFactory(),
                args=(q, e, self.timeout, msg.key),
            )
            p.start()
            self.data[msg.key] = workeritem(p, q, e, time.time())
        self.logger.debug(
            f"{msg.key}: approx queue size {self.data[msg.key].q.qsize()}"
        )
        if self.data[msg.key].q.empty():
            self.logger.debug(f"{msg.key}: empty, adding new")
            self.data[msg.key].q.put(msg)
        self.data[msg.key].t = time.time()

    def handleKill(self, msg) -> None:
        if msg.key in self.data:
            self.data[msg.key].e.set()

    def msgworker(self) -> None:
        """
        Handle client inputs from the queue.
        """

        while True:
            self.logger.debug("restarting loop")
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
        key: str = "",
        job: str = "",
        urgency: str = "critical",
        errcode: int = -1000,
        msg: str = "",
    ) -> None:
        if self.notification_cmd is None:
            return
        try:
            self.logger.debug(
                f"sending message {job=}, {key=}, {msg=}, {urgency=}, {errcode=}"
            )
            subprocess.run(
                shlex.split(
                    self.notification_cmd.format(
                        key=key,
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
            while True:
                if e.is_set():
                    break
                if retry_timeout_index + 1 < len(self.retry_sequence):
                    retry_timeout_index += 1
                success = True
                for job in msg.cmd:
                    logger.debug(f"running job: {job} with timeout {self.job_timeout}")
                    try:
                        proc = subprocess.run(
                            job, capture_output=True, timeout=self.job_timeout
                        )
                        if proc.returncode != 0:
                            success = False
                            logger.error(
                                f"{proc.returncode=}, {proc.stdout=}, {proc.stderr=}"
                            )
                            if retry_timeout_index + 1 >= self.notify_on_counter:
                                self.sendNotification(
                                    key=msg.key,
                                    job=str(job),
                                    msg=f"{proc.stderr.decode('utf-8')} - {proc.stdout.decode('utf-8')}",
                                    errcode=proc.returncode,
                                )
                            break
                    except Exception as error:
                        logger.error(f"{job}'s subprocess failed with {error}")
                        self.sendNotification(
                            key=msg.key,
                            job=str(job),
                            msg=f"subprocess failed with {error}",
                        )
                        success = False
                        break

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
                except queue.Empty:
                    logger.info("closing process")
                    break
            self.q.put(Msg(key="", cmd=[[]], action=ActionType.CLEAN))

        return worker

    def cleanup(self):
        self.logger.debug("cleanup underway, {self.data.keys()}")
        toclean = []
        for key, val in self.data.items():
            if not val.p.is_alive():
                toclean.append(key)

        for key in toclean:
            del self.data[key]
        self.logger.debug("cleanup finished, {self.data.keys()}")
