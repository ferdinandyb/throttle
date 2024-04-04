"""
Based on the argparse implementation of _AppendAction

https://github.com/python/cpython/blob/main/Lib/argparse.py
"""
import argparse


def _copy_items(items):
    if items is None:
        return []
    # The copy module is used only in the 'append' and 'append_const'
    # actions, and it is needed only when the default value isn't a list.
    # Delay its import for speeding up the common case.
    if type(items) is list:
        return items[:]
    import copy

    return copy.copy(items)


class storeJob(argparse._AppendAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        self.append(namespace, "job", values)
        self.append(namespace, "notifications", 1)

    def append(self, namespace, dest, values):
        items = getattr(namespace, dest, None)
        items = _copy_items(items)
        items.append(values)
        setattr(namespace, dest, items)


class storeSilentJob(storeJob):
    def __call__(self, parser, namespace, values, option_string=None):
        self.append(namespace, "job", values)
        self.append(namespace, "notifications", 0)
