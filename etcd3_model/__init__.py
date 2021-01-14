"""
Initialization for the Compute Node Uprade Service (CRUS)

Copyright 2019, Cray Inc. All rights reserved.
"""
from .etcd_instance import create_instance
from .etcd3_model import (
    Etcd3Model,
    Etcd3Attr,
    DELETING,
    UPDATING,
    READY,
    STATE_DESCRIPTION,
    MESSAGES_DESCRIPTION
)
from .utils import clean_desc
from .config import Config
