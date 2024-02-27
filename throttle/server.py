from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import socket
from pathlib import Path


def handleMsg(arg):
    print(arg)


def start_server(socketpath):
    if Path(socketpath).exists():
        Path(socketpath).unlink()

    srv = SimpleJSONRPCServer(socketpath, address_family=socket.AF_UNIX)
    srv.register_function(handleMsg, "handle")
    srv.serve_forever()
