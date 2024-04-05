import logging
import os
import socket
import time
from multiprocessing import Process, Queue, active_children
from pathlib import Path
from typing import Any, Callable

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

from . import loglib
from .commandworker import CommandWorker
from .structures import Msg


def ipcworker(socketpath: Path, handleMsg: Callable, handleInfo: Callable) -> None:
    socketpath.parent.mkdir(parents=True, exist_ok=True)
    if Path(socketpath).exists():
        Path(socketpath).unlink()
    logger = logging.getLogger("ipc_worker")
    srv = SimpleJSONRPCServer(str(socketpath), address_family=socket.AF_UNIX)
    srv.register_function(handleMsg, "handle")
    srv.register_function(handleInfo, "info")
    logger.info(f"starting up server on socket: {socketpath}")
    srv.serve_forever()


def start_server(socketpath: Path, loglevel) -> None:
    ipcqueue: Queue[Msg] = Queue()
    logqueue: Queue[Any] = Queue()
    comqueue: Queue[Any] = Queue()
    loggerp = Process(target=loglib.consumer, args=(logqueue,))
    loggerp.start()

    msgworker = CommandWorker(ipcqueue, logqueue, comqueue)
    loglib.publisher_config(logqueue, loglevel)
    logger = logging.getLogger("server")
    logger.debug(os.environ)

    def handleMsg(msg) -> None:
        ipcqueue.put(Msg(**msg))

    def handleInfo(msg):
        print("handling")
        ipcqueue.put(Msg(**msg))
        return comqueue.get()

    p_ipc = Process(
        target=ipcworker,
        args=(socketpath, handleMsg, handleInfo),
    )
    p_msg = Process(target=msgworker.msgworker, args=())
    p_ipc.start()
    p_msg.start()
    while True:
        time.sleep(1)
        if not active_children():
            break
