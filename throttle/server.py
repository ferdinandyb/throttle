from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import socket
from multiprocessing import Process, Manager
from pathlib import Path


def ipcworker(socketpath, handleMsg):
    if Path(socketpath).exists():
        Path(socketpath).unlink()

    srv = SimpleJSONRPCServer(socketpath, address_family=socket.AF_UNIX)
    srv.register_function(handleMsg, "handle")
    srv.serve_forever()


def msgworker(q):
    while True:
        msg = q.get()
        print("worker", msg)


def start_server(socketpath):
    with Manager() as manager:
        queue = manager.Queue()

        def handleMsg(msg):
            queue.put(msg)

        p_ipc = Process(
            target=ipcworker,
            args=(socketpath, handleMsg),
        )
        p_msg = Process(target=msgworker, args=(queue,))

        p_ipc.start()
        p_msg.start()
        p_ipc.join()
        p_msg.join()
