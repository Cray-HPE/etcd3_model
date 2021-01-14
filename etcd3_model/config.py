"""The etcd3_model Config class stores application configuration locally

Copyright 2019, Cray Inc. All rights reserved.
"""
import os
from .version import VERSION


class Config:
    """etcd3_model Config class stores application configuration passed in
    as an app.config dictionary from the application as it applies to
    ETCD.  Specificially, this will be the settings:

        ETCD_HOST - the host name or IP where the etcd instance (if any)
                    is running
        ETCD_PORT - the port on which the etcd instance (if any) is running
        ETCD3_MOCK_CLIENT - boolean indicating whether to mock the etcd
                            instance
        ETCD3_MODEL_VERSION - the current version of the module.

    """
    ETCD_HOST = os.environ.get('ETCD_HOST', "localhost")
    ETCD_PORT = os.environ.get('ETCD_PORT', "2379")
    ETCD_MOCK_CLIENT = os.environ.get("ETCD_MOCK_CLIENT",
                                      "no").lower() == 'yes'
    ETCD3_MODEL_VERSION = VERSION
