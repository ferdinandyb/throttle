import logging
import socket
from multiprocessing import Process, Queue
from pathlib import Path
from typing import Callable, Any

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer

from . import loglib
from .commandworker import CommandWorker
from .structures import Msg, ActionType


def ipcworker(socketpath: Path, handleMsg: Callable, logqueue: Queue) -> None:
    if Path(socketpath).exists():
        Path(socketpath).unlink()
    loglib.publisher_config(logqueue)
    logger = logging.getLogger("ipc_worker")
    srv = SimpleJSONRPCServer(str(socketpath), address_family=socket.AF_UNIX)
    srv.register_function(handleMsg, "handle")
    logger.info(f"starting up server on socket: {socketpath}")
    srv.serve_forever()


def start_server(socketpath: Path) -> None:
    ipcqueue: Queue[Msg] = Queue()
    logqueue: Queue[Any] = Queue()
    loggerp = Process(target=loglib.consumer, args=(logqueue,))
    loggerp.start()

    def handleMsg(msg) -> None:
        ipcqueue.put(Msg(**msg))

    p_ipc = Process(
        target=ipcworker,
        args=(socketpath, handleMsg, logqueue),
    )
    msgworker = CommandWorker(ipcqueue, logqueue)
    p_msg = Process(target=msgworker.msgworker, args=())

    p_ipc.start()
    p_msg.start()
    p_ipc.join()
    p_msg.join()
