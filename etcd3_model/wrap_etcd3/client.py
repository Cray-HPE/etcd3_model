"""
Mocking for etcd3 clients

Copyright 2018, Cray Inc. All rights reserved.
"""
import threading
from time import time, sleep
from .events import PutEvent, DeleteEvent


class CommonLock:
    """A mock version of the shared mechanism underlying the etcd3 Lock
    object.  There is one of these per named lock.

    """
    def __init__(self, name, ttl=60, etcd_client=None):
        """Constructor

        Parameters:

        name

            unique name of the lock on which all instances of the same
            lock will coordinate locking.

        ttl

            Time to Live (TTL) of the lock in seconds.

        etcd_client

            The etcd_client where this lock lives.

        """
        # Each successful acquisition gets a unique number (always
        # incremented) which it uses to claim ownership in checking
        # for is_acquired() or for releasing() the lock.
        self.acquire_counter = 0
        self.name = name
        self.ttl = ttl
        self.etcd_client = etcd_client
        self.release_time = None
        # used for thread safety, not part of the mechanism:
        self.thread_lock = threading.Lock()

    def is_acquired(self, owner_counter):
        """Determine whether the lock is currently being held or not (i.e. TTL
        is there and not expired).

        """
        if owner_counter != self.acquire_counter:
            # Not the owner of the lock
            return False
        with self.thread_lock:
            if self.release_time is not None and self.release_time >= time():
                return True
        return False

    def acquire(self, timeout=None):
        """Acquire the lock using the specified timeout and the lock's TTL
        value.

        """
        give_up = time() + timeout if timeout is not None else None
        while True:
            with self.thread_lock:
                if self.release_time is None or self.release_time < time():
                    # Either the lock was released or reached its TTL.
                    # Take it.
                    self.release_time = time() + self.ttl
                    self.acquire_counter += 1
                    return self.acquire_counter
            if give_up is not None and time() >= give_up:
                # Failed to acquire the lock, return None
                return None
            sleep(0.1)  # try not to be a CPU hog

    def release(self, owner_counter):
        """Release the current lock if the caller owns it.

        """
        if owner_counter != self.acquire_counter:
            # Not the owner of the lock
            return False
        with self.thread_lock:
            # Clear the lock by removing the TTL
            self.release_time = None
            return True


class Lock:
    """Mock implementation of the etcd3 Lock object.

    """
    def __init__(self, common_lock):
        """ Constructor

        """
        self.common_lock = common_lock
        self.owner_counter = None

    def __enter__(self):
        """The enter operation to make this a context manager.

        """
        self.acquire()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """The exit function to make this a context manager.

        """
        self.release()
        return False  # allow exceptions to propagate (if any)

    def acquire(self, timeout=None):
        """Acquire the lock using the specified timeout and the lock's TTL
        value.

        """
        self.owner_counter = self.common_lock.acquire(timeout)
        return self.owner_counter is not None

    def is_acquired(self):
        """Determine whether this Lock instance acquired the common lock and
        it is still held or not.

        """
        return self.common_lock.is_acquired(self.owner_counter)

    def release(self):
        """Release the lock.

        """
        self.common_lock.release(self.owner_counter)
        self.owner_counter = None


class Etcd3KeyMetadata:
    """A mock version of the Etcd3Metadata class to give us something
    similar to yield from getprefix.

    """
    def __init__(self, key):
        self.key = key
        self.create_revision = 0
        self.mod_revision = 0
        self.version = 0
        self.lease_id = None
        self.response_header = None


class Etcd3Client:
    """Fake etcd client that can be used for standalone testing of
    interactions with ETCD.  Supports the subset of the ETCD client
    API necessary for testing.  As new uses of ETCD come along,
    add them here for testing.

    """
    def __init__(self, **kwargs):
        """Create the mock etcd3 client which is implemented as a keystore
        that simulates ETCD storage.

        """
        # Set up the keystore that will hold the data
        self.keystore = {}

        # Lock table for this client
        self.lock_table = {}

        # To be thread-safe, we need to be able to lock when doing
        # things, make a global lock
        self.thread_lock = threading.Lock()

        # Set up a place to keep watches, indexed by callback id.  A
        # watch is a tuple of a key / prefix and a callback.
        self.next_watch_id = 0
        self.watches = {}

        # Pick up any settings that came in as keyword args
        for attr in kwargs:
            setattr(self, attr, kwargs[attr])

    def __check_watch(self, key, event):
        """Check for and generate a watch callback if 'key' is found to be in
        range of one of the watches that have been set.  The event in
        'event' should be either a 'PutEvent' or a 'DeleteEvent'
        depending on whether the operation was a put or a delete on
        the key.  This should only be called with the lock released
        and it will call the callback with the lock released)

        """
        callback = None
        with self.thread_lock:
            for watch_id in self.watches:
                begin, end, callback = self.watches[watch_id]
                if begin <= key < end:
                    break
                callback = None
        if callback is not None:
            # pylint: disable=not-callable
            callback(event)

    # pylint: disable=unused-argument
    def get_prefix(self, prefix, sort_order=None, sort_target='key'):
        """The get_prefix() operation (minimally implemented, no sorting is
        provided -- add it if you need it later).

        """
        keys = []
        # Lock for the scan to prevent the dictionary from changing
        # size
        prefix = bytes(prefix, 'utf-8')
        with self.thread_lock:
            keys = [key for key in self.keystore if prefix in key]

        # Now go through and yield back the data we think we found
        for key in keys:
            # Can't use 'with' locking here because yield does not
            # release the lock.  Instead we have to lock for each
            # iteration.  This prevents the keystore from changing
            # while we check for and grab data from a key.
            self.thread_lock.acquire()

            # Need to re-check each time because a key might have been
            # deleted since the previous iteration.
            if key in self.keystore:
                item = (self.keystore[key], Etcd3KeyMetadata(key))
                self.thread_lock.release()
                yield item
            else:  # pragma no unit test
                # We hit a race condition where a key is removed from
                # the keystore after the start of the get_prefix()
                # call, in which case we release the lock and iterate
                # again hoping for better luck on the next key.
                self.thread_lock.release()

    def get(self, key):
        """ The get operation.
        """
        key = bytes(key, 'utf-8')
        with self.thread_lock:
            if key not in self.keystore:
                return (None, None)
            return (self.keystore[key], Etcd3KeyMetadata(key))

    # pylint: disable=unused-argument
    def put(self, key, value, lease=None):
        """The 'put' operation (minimally supported, no locking semantics, no
        watch semantics, and no versioning semantics -- add those as
        needed).

        """
        key = bytes(key, 'utf-8')
        value = bytes(value, 'utf-8')
        event = None
        with self.thread_lock:
            self.keystore[key] = value
            event = PutEvent(key=key, value=self.keystore[key])
        self.__check_watch(key, event)

    def delete(self, key):
        """The 'delete' operation, delete the key / value from the keystore
        and return True or just return False if the key wasn't there
        to begin with.

        """
        ret = False
        event = None
        key = bytes(key, 'utf-8')
        with self.thread_lock:
            if key in self.keystore:
                event = DeleteEvent(key)
                del self.keystore[key]
                ret = True
        if ret:
            self.__check_watch(key, event)
        return ret

    def add_watch_callback(self, key, callback, range_end=None):
        """ Add a watch callback on a key or range of keys.
        """
        ret = 0
        key = bytes(key, 'utf-8')
        if range_end is None:  # pragma no cover
            # The etcd3_model code never sets up a range with node end
            # specified (i.e. a specifically single element range) but
            # handle it anyway.
            range_end = key
        else:
            range_end = bytes(range_end, 'utf-8')
        with self.thread_lock:
            ret = self.next_watch_id
            self.next_watch_id += 1
            self.watches[ret] = (key, range_end, callback)
        return ret

    def lock(self, name, ttl=60):
        """Create a Lock() instance suitable for use as a context manager.

        """
        with self.thread_lock:
            if name not in self.lock_table:
                self.lock_table[name] = CommonLock(name, ttl=ttl,
                                                   etcd_client=self)
            return Lock(self.lock_table[name])


def client(host='localhost', port=2379, **kwargs):
    """Construct a mock Etcd3Client and return it.

    """
    return Etcd3Client(host=host, port=port, **kwargs)
