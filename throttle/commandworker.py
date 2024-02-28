import queue
import subprocess
import time
from dataclasses import dataclass
from multiprocessing import Process, Queue
from pathlib import Path

import toml
from xdg import BaseDirectory


@dataclass
class workeritem:
    p: Process
    q: Queue
    t: float


class CommandWorker:
    def __init__(self, queue):
        self.q = queue
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
        print("checking", self.filters)
        for item in self.filters:
            print(item)
            if re.search(item["regex"], shlex.join(msg)):
                print("match")
                return shlex.split(item["result"])
        return msg

    def msgworker(self):
        """
        Handle client inputs from the queue.
        """
        while True:
            print("restarting loop")
            msg = self.q.get()
            msg = self.checkregex(msg)
            curtime = time.time()
            print("worker", curtime, msg)
            key = shlex.join(msg)
            if key not in self.data or not self.data[key].p.is_alive():
                print(f"{key}: doesn't exist or finished, creating")
                q = Queue()
                p = Process(
                    target=self.workerFactory(),
                    args=(q, self.timeout),
                )
                p.start()
                self.data[key] = workeritem(p, q, time.time())
            print(f"{key}: approx queue size {self.data[key].q.qsize()}")
            if self.data[key].q.empty():
                print(f"{key}: empty, adding new")
                self.data[key].q.put(msg)
            self.data[key].t = time.time()

            self.cleanup()

    def workerFactory(self):
        """
        Factory for handling each type of client input.
        """

        def worker(q, timeout):
            retry_sequence = self.retry_sequence
            while True:
                try:
                    msg = q.get(timeout=timeout)
                    print("starting", time.time(), msg)
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
                        print(time.time(), proc.returncode, stdout, stderr)
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
                    print("finished", time.time(), msg)
                except queue.Empty:
                    print("finishing")
                    break

        return worker

    def cleanup(self):
        print("cleanup underway", self.data.keys())
        toclean = []
        for key, val in self.data.items():
            if not val.p.is_alive():
                toclean.append(key)

        for key in toclean:
            del self.data[key]
        print("cleanup finished", self.data.keys())
