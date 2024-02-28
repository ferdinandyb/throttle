import logging
import logging.handlers
from pathlib import Path

from xdg import BaseDirectory


def consumer(queue):
    root = logging.getLogger()
    logfolder = Path(BaseDirectory.xdg_state_home) / "throttle"
    logfolder.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(logfolder / "throttle.log", "a", 300, 10)
    f = logging.Formatter(
        "%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s"
    )
    h.setFormatter(f)
    root.addHandler(h)
    while True:
        try:
            record = queue.get()
            # We send this as a sentinel to tell the listener to quit.
            if record is None:
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)  # No level or filter logic applied - just do it!
        except Exception:
            import sys
            import traceback

            print("Whoops! Problem:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)


def publisher_config(queue):
    h = logging.handlers.QueueHandler(queue)  # Just the one handler needed
    root = logging.getLogger()
    root.addHandler(h)
    # send all messages, for demo; no other level or filter logic applied.
    root.setLevel(logging.DEBUG)
