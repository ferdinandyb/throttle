from jsonrpclib import ServerProxy


def send_message(socketpath, msg):
    client = ServerProxy(f"unix+http://{socketpath}")
    client.handle(msg)
    client("close")()
