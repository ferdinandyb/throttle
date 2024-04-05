import os
import sys
import time

from prettytable import MARKDOWN, PLAIN_COLUMNS, PrettyTable


def formatTable(table, format):
    if format == "markdown":
        table.set_style(MARKDOWN)
        format = "text"
    if format == "plain":
        table.set_style(PLAIN_COLUMNS)
        format = "text"
    return table.get_formatted_string(format)


def parse_stat(stats, format):
    maxwidth = None
    if sys.stdout.isatty():
        width, _ = os.get_terminal_size()
        maxwidth = width - 40

    curtime = time.time()
    total_sec = curtime - stats["start"]
    table = PrettyTable()
    table.field_names = ["job", "run", "total", "throttle", "avg/min"]
    for key, val in stats["jobs"].items():
        r = val["run"]
        tot = val["total"]
        t = total_sec / 60
        throttle = (tot - r) / tot
        avg = r / t
        table.add_row([key[:maxwidth], r, tot, throttle, avg])
    table.sortby = "throttle"
    table.reversesort = True
    table.float_format = ".2"
    table.align["job"] = "l"
    return formatTable(table, format)


def parse_status(status, format):
    maxwidth = None
    if sys.stdout.isatty():
        width, _ = os.get_terminal_size()
        maxwidth = width - 20

    curtime = time.time()
    table = PrettyTable()
    table.field_names = ["job", "queue size", "uptime (s)"]
    for key, val in status.items():
        uptime = curtime - val["uptime"]
        table.add_row([key[:maxwidth], val["queuesize"], uptime])
    table.sortby = "uptime (s)"
    table.reversesort = True
    table.float_format = ".0"
    table.align["job"] = "l"
    return formatTable(table, format)
