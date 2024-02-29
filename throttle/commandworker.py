import logging
import queue
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from multiprocessing import Process, Queue, Event
from multiprocessing.synchronize import Event as SyncEvent
from pathlib import Path
from typing import Dict, List

import toml
from xdg import BaseDirectory

from . import loglib
from .structures import Msg, ActionType


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

    def runworkerFactory(self):
        """
        Factory for handling each type of jobs.
        """

        def handlejobs(msg: Msg, e, logger):
            retry_timeout_index = -1
            while True:
                if e.is_set():
                    break
                if retry_timeout_index + 1 < len(self.retry_sequence):
                    retry_timeout_index += 1
                for job in msg.cmd:
                    logger.debug(f"running job: {job}")
                    proc = subprocess.Popen(
                        job, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    stdout, stderr = proc.communicate()
                    if proc.returncode != 0:
                        break
                if proc.returncode == 0:
                    break
                logger.error(f"{proc.returncode=}, {stdout=}, {stderr=}")
                if self.notification_cmd is not None:
                    subprocess.Popen(
                        shlex.split(
                            self.notification_cmd.format(
                                errcode=proc.returncode,
                                stdout=stdout.decode("utf-8"),
                                stderr=stderr.decode("utf-8"),
                            )
                        )
                    )
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
