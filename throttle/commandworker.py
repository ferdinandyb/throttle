import logging
import queue
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from multiprocessing import Process, Queue
from pathlib import Path

import toml
from xdg import BaseDirectory

from . import loglib


@dataclass
class workeritem:
    p: Process
    q: Queue
    t: float


class CommandWorker:
    def __init__(self, queue, logqueue):
        self.q = queue
        self.logqueue = logqueue
        loglib.publisher_config(self.logqueue)
        self.logger = logging.getLogger("msg_worker")
        self.data = {}
        self.timeout = 20
        self.filters = []
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

    def checkregex(self, msg):
        self.logger.debug(f"checking: {self.filters}")
        for item in self.filters:
            if re.search(item["regex"], shlex.join(msg)):
                self.logger.info(f"regex rewrite {msg} -> {item['result']}")
                return shlex.split(item["result"])
        return msg

    def msgworker(self):
        """
        Handle client inputs from the queue.
        """

        while True:
            self.logger.debug("restarting loop")
            msg = self.q.get()
            msg = self.checkregex(msg)
            self.logger.info(f"handling {msg}")
            key = shlex.join(msg)
            if key not in self.data or not self.data[key].p.is_alive():
                self.logger.debug(f"{key}: doesn't exist or finished, creating")
                q = Queue()
                p = Process(
                    target=self.workerFactory(),
                    args=(q, self.timeout, key, self.logqueue),
                )
                p.start()
                self.data[key] = workeritem(p, q, time.time())
            self.logger.debug(f"{key}: approx queue size {self.data[key].q.qsize()}")
            if self.data[key].q.empty():
                self.logger.debug(f"{key}: empty, adding new")
                self.data[key].q.put(msg)
            self.data[key].t = time.time()

            self.cleanup()

    def workerFactory(self):
        """
        Factory for handling each type of client input.
        """

        def worker(q, timeout, name, logqueue):
            retry_sequence = self.retry_sequence
            loglib.publisher_config(logqueue)

            logger = logging.getLogger(f"{name.replace(' ','_')}_worker")
            counter = 0
            logger.info("starting process")
            while True:
                try:
                    msg = q.get(timeout=timeout)
                    counter += 1
                    logger.info(f"start run no: {counter}")
                    retry_timeout_index = -1
                    while True:
                        if retry_timeout_index + 1 < len(retry_sequence):
                            retry_timeout_index += 1
                        proc = subprocess.Popen(
                            msg, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        )
                        stdout, stderr = proc.communicate()
                        if proc.returncode == 0:
                            break
                        logger.debug(f"{proc.returncode=}, {stdout=}, {stderr=}")
                        if self.notification_cmd is not None:
                            subprocess.Popen(
                                shlex.split(
                                    self.notification_cmd.format(
                                        errcode=proc.returncode,
                                        stdout=stdout,
                                        stderr=stderr,
                                    )
                                )
                            )
                        time.sleep(retry_sequence[retry_timeout_index])
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
