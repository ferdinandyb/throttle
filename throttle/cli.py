from throttle.server import start_server
from throttle.client import send_message
from xdg import BaseDirectory


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true")
    args, unknownargs = parser.parse_known_args()
    socketpath = f"{BaseDirectory.get_runtime_dir()}/throttle.sock"
    if args.server:
        start_server(socketpath)
        return

    send_message(socketpath, unknownargs)


if __name__ == "__main__":
    main()
