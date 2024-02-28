from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import socket
from multiprocessing import Process, Queue
from pathlib import Path
from dataclasses import dataclass
import queue
import re
import time
import subprocess
import toml
from xdg import BaseDirectory


def ipcworker(socketpath, handleMsg):
    if Path(socketpath).exists():
        Path(socketpath).unlink()

    srv = SimpleJSONRPCServer(socketpath, address_family=socket.AF_UNIX)
    srv.register_function(handleMsg, "handle")
    srv.serve_forever()


@dataclass
class workeritem:
    p: Process
    q: Queue
    t: float


class MessageWorker:
    def __init__(self, queue):
        self.q = queue
        self.data = {}
        self.timeout = 20
        self.filters = []
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

    def checkregex(self, msg):
        print("checking", self.filters)
        for item in self.filters:
            print(item)
            if re.search(item["regex"], " ".join(msg)):
                print("match")
                return item["result"].split(" ")
        return msg

    def msgworker(self):
        while True:
            print("restarting loop")
            msg = self.q.get()
            msg = self.checkregex(msg)
            curtime = time.time()
            print("worker", curtime, msg)
            key = " ".join(msg)
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
                        if proc.returncode:
                            print(time.time(), proc.returncode, stdout, stderr)
                            time.sleep(retry_sequence[retry_timeout_index])
                        else:
                            break
                    print("finished", time.time(), msg)
                except queue.Empty:
                    print("finishing")
                    break

        return worker

    def cleanup(self):
        # go through process and queues that haven't been touch in X minutes
        print("cleanup underway", self.data.keys())
        toclean = []
        for key, val in self.data.items():
            if not val.p.is_alive():
                toclean.append(key)

        for key in toclean:
            del self.data[key]
        print("cleanup finished", self.data.keys())


def start_server(socketpath):
    queue = Queue()

    def handleMsg(msg):
        queue.put(msg)

    p_ipc = Process(
        target=ipcworker,
        args=(socketpath, handleMsg),
    )
    msgworker = MessageWorker(queue)
    p_msg = Process(target=msgworker.msgworker, args=())

    p_ipc.start()
    p_msg.start()
    p_ipc.join()
    p_msg.join()
