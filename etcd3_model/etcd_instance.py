"""Provide a function for obtaining a properly wrapped ETCD instance
for use in Etcd3Model derived classes.

Copyright 2019, Cray Inc. All rights reserved.

"""
from .config import Config
from .wrap_etcd3 import client


def create_instance():
    """Create a new etcd3 client using the configured ETCD_HOST and
    ETCD_PORT values set by:

         etcd3_model.Config(configuration)

    which should have been called before this method is called.

    """
    return client(Config.ETCD_HOST, Config.ETCD_PORT)
