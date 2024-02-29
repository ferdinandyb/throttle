import logging
import queue
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from multiprocessing import Process, Queue
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
    t: float


class CommandWorker:
    def __init__(self, queue: Queue, logqueue: Queue):
        self.q = queue
        self.logqueue = logqueue
        loglib.publisher_config(self.logqueue)
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
        if msg.key not in self.data or not self.data[msg.key].p.is_alive():
            self.logger.debug(f"{msg.key}: doesn't exist or finished, creating")
            q: Queue[Msg] = Queue()
            p = Process(
                target=self.runworkerFactory(),
                args=(q, self.timeout, msg.key, self.logqueue),
            )
            p.start()
            self.data[msg.key] = workeritem(p, q, time.time())
        self.logger.debug(
            f"{msg.key}: approx queue size {self.data[msg.key].q.qsize()}"
        )
        if self.data[msg.key].q.empty():
            self.logger.debug(f"{msg.key}: empty, adding new")
            self.data[msg.key].q.put(msg)
        self.data[msg.key].t = time.time()

    def msgworker(self) -> None:
        """
        Handle client inputs from the queue.
        """

        while True:
            self.logger.debug("restarting loop")
            msg: Msg = self.q.get()
            msg = self.checkregex(msg)
            self.logger.info(f"handling {msg}")
            if msg.action == ActionType.RUN:
                self.handleRun(msg)

            self.cleanup()

    def runworkerFactory(self):
        """
        Factory for handling each type of jobs.
        """

        def handlejobs(msg: Msg, logger, retry_sequence):
            retry_timeout_index = -1
            while True:
                if retry_timeout_index + 1 < len(retry_sequence):
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
                logger.debug(f"{proc.returncode=}, {stdout=}, {stderr=}")
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
                time.sleep(retry_sequence[retry_timeout_index])

        def worker(q, timeout, name, logqueue) -> None:
            self.retry_sequence
            loglib.publisher_config(logqueue)

            logger = logging.getLogger(f"{name.replace(' ','_')}_worker")
            counter = 0
            logger.info("starting process")

            while True:
                try:
                    msg = q.get(timeout=timeout)
                    counter += 1
                    logger.info(f"start run no: {counter}")
                    handlejobs(msg, logger, self.retry_sequence)
                    logger.info(f"finish run no: {counter}")
                except queue.Empty:
                    logger.info("closing process")
                    break

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
