"""
Mock etcd3 Event and related handling

Copyright 2018, Cray Inc. All rights reserved.
"""


class Event:
    """Limited mock up of the etcd3 event key structure

    """
    def __init__(self, key, value=b''):
        self.key = key
        self.value = value


class PutEvent(Event):
    """Event wrapper to distinguish put events from watch.

    """


class DeleteEvent(Event):
    """Event wrapper to distinguish delete events from watch.

    """
