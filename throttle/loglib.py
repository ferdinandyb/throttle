import logging
import logging.handlers
from pathlib import Path

from xdg import BaseDirectory


def consumer(queue):
    root = logging.getLogger()
    logfolder = Path(BaseDirectory.xdg_state_home) / "throttle"
    logfolder.mkdir(parents=True, exist_ok=True)
    filehandler = logging.handlers.RotatingFileHandler(
        logfolder / "throttle.log", "a", 1024 * 1024 * 10, 3
    )
    f = logging.Formatter("%(asctime)s - %(name)s - %(levelname)-8s - %(message)s")
    filehandler.setFormatter(f)
    root.addHandler(filehandler)
    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(f)
    root.addHandler(streamhandler)
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


def publisher_config(queue, loglevel=logging.INFO):
    h = logging.handlers.QueueHandler(queue)  # Just the one handler needed
    root = logging.getLogger()
    root.addHandler(h)
    # send all messages, for demo; no other level or filter logic applied.
    root.setLevel(loglevel)
