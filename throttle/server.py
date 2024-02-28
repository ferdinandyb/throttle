import socket
from multiprocessing import Process, Queue
from pathlib import Path

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
from logger import loggerworker

from commandworker import CommandWorker


def ipcworker(socketpath, handleMsg):
    if Path(socketpath).exists():
        Path(socketpath).unlink()

    srv = SimpleJSONRPCServer(socketpath, address_family=socket.AF_UNIX)
    srv.register_function(handleMsg, "handle")
    srv.serve_forever()


def start_server(socketpath):
    ipcqueue = Queue()
    logqueue = Queue()
    loggerp = Process(target=loggerworker, args=(logqueue,))

    def handleMsg(msg):
        ipcqueue.put(msg)

    p_ipc = Process(
        target=ipcworker,
        args=(socketpath, handleMsg),
    )
    msgworker = CommandWorker(ipcqueue)
    p_msg = Process(target=msgworker.msgworker, args=())

    p_ipc.start()
    p_msg.start()
    p_ipc.join()
    p_msg.join()
