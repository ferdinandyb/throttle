from .server import start_server
from pathlib import Path
from .client import send_message
from xdg import BaseDirectory


def main():
    import argparse

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-s", "--server", action="store_true")
    group.add_argument("-c", "--cmd", action="append")
    group.add_argument("-k", "--kill", action="store_true")
    args, unknownargs = parser.parse_known_args()
    socketpath = Path(BaseDirectory.get_runtime_dir()) / "throttle.sock"
    if args.server:
        start_server(socketpath)
        return

    send_message(socketpath, args.kill, args.cmd, unknownargs)


if __name__ == "__main__":
    main()
