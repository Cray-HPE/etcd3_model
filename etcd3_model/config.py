"""The etcd3_model Config class stores application configuration locally

MIT License

(C) Copyright [2020] Hewlett Packard Enterprise Development LP

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE."""
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
