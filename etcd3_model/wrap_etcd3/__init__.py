"""Wrap the etcd3 imports so we can either pick up the mock etcd3
(which is implemented in this directory) and the real etcd3 which is
provided as a library.

Copyright 2019, Cray Inc. All rights reserved.

"""
from ..config import Config
if Config.ETCD_MOCK_CLIENT:
    from .client import client
    from .events import PutEvent, DeleteEvent
else:  # pragma no unit test
    from etcd3.client import client
    from etcd3.events import PutEvent, DeleteEvent
