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


def ipcworker(socketpath: Path, handleMsg: Callable) -> None:
    socketpath.parent.mkdir(parents=True, exist_ok=True)
    if Path(socketpath).exists():
        Path(socketpath).unlink()
    logger = logging.getLogger("ipc_worker")
    srv = SimpleJSONRPCServer(str(socketpath), address_family=socket.AF_UNIX)
    srv.register_function(handleMsg, "handle")
    logger.info(f"starting up server on socket: {socketpath}")
    srv.serve_forever()


def start_server(socketpath: Path, loglevel) -> None:
    ipcqueue: Queue[Msg] = Queue()
    logqueue: Queue[Any] = Queue()
    loggerp = Process(target=loglib.consumer, args=(logqueue,))
    loggerp.start()

    msgworker = CommandWorker(ipcqueue, logqueue)
    loglib.publisher_config(logqueue, loglevel)
    logger = logging.getLogger("server")
    logger.debug(os.environ)

    def handleMsg(msg) -> None:
        ipcqueue.put(Msg(**msg))

    p_ipc = Process(
        target=ipcworker,
        args=(socketpath, handleMsg),
    )
    p_msg = Process(target=msgworker.msgworker, args=())
    p_ipc.start()
    p_msg.start()
    while True:
        time.sleep(1)
        if not active_children():
            break
