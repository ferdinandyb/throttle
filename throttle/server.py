from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import socket
from multiprocessing import Process, Queue
from pathlib import Path
import time
import subprocess


def ipcworker(socketpath, handleMsg):
    if Path(socketpath).exists():
        Path(socketpath).unlink()

    srv = SimpleJSONRPCServer(socketpath, address_family=socket.AF_UNIX)
    srv.register_function(handleMsg, "handle")
    srv.serve_forever()


class MessageWorker:
    def __init__(self, queue):
        self.q = queue
        self.data = {}

    def msgworker(self):
        while True:
            print("restarting loop")
            msg = self.q.get()
            curtime = time.time()
            print("worker", curtime, msg)
            self.executeworker(msg)

    def executeworker(self, msg):
        def runner(args):
            print("started")
            proc = subprocess.Popen(args)
            proc.wait()
            print("finished in runner")
            self.finished()

        p = Process(target=runner, args=(msg,))
        p.start()
        return p

    def finished(self):
        print("done")


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
