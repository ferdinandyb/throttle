from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import socket
from multiprocessing import Process, Queue
from pathlib import Path
from dataclasses import dataclass
import queue
import time
import subprocess


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

    def msgworker(self):
        while True:
            print("restarting loop")
            msg = self.q.get()
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
            while True:
                try:
                    msg = q.get(timeout=timeout)
                    print("starting", time.time(), msg)
                    proc = subprocess.Popen(msg)
                    proc.wait()
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
