"""
Base class implementing class level locking capability.

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


class LockHolder:
    """Wrapper for etcd3 locks to allow them to be acquired with a timeout
    on the acquisition for non-blocking lock checks.

    """
    def __init__(self, etcd, name, ttl=60, timeout=None):
        """ Constructor

        """
        self.my_lock = etcd.lock(name, ttl=ttl)
        self.timeout = timeout

    def acquire(self, ):
        """Manually acquire the lock for this instance, obtained by calling
        lock() above.  The timeout and TTL set in the lock() call will
        be used for the acquisition.

        """
        self.my_lock.acquire(self.timeout)
        return self

    def release(self):
        """Manually release the lock for this instance.

        """
        return self.my_lock.release()

    def is_acquired(self):
        """Find out whether the lock for this instance is currently acquired
        (uesful when using non-blocking or timed acquisitions).

        """
        return self.my_lock.is_acquired()

    def __enter__(self):
        """Acquire the lock as a context manager.

        """
        return self.acquire()

    def __exit__(self, exception_type, exception_value, traceback):
        """ Release the lock at the end of a managed context.

        """
        self.release()
        return False


class Lockable:
    """Base class with a lock() method that produces distinct locks per
    object-id in ETCD for use with 'with'.  Call the lock() method on an
    instance of the class to obtain the lock.

    Example:

    class Foo(Lockable):
        def __init__(self):
             assert self  # keep lint happy

    my_instance = Foo()
    with my_instance.lock():
        print("I am in the lock"
    print("No longer in the lock")

    """
    def __init__(self, name, etcd):
        """Constructor

        The paramters are:

        name

            The unique name that identifies the resource to be locked
            by this partitcular lockable instance.

        etcd

            The ETCD client to be used for creating a lock in this
            particular lockable instance.

        """
        self.name = name
        self.etcd = etcd

    def lock(self, ttl=60, timeout=None):
        """Method to use with the 'with' statement for locking the instance
        resource.  This creates the lock that will be shared across
        all instances (through ETCD).  The parameters are as follows:

        ttl

            The time-to-live (TTL) of a lock acquisition on this
            lock. This is expressed in seconds.  If TTL expires while
            the lock is held, the lock is dropped allowing someone
            else to acquire it.  To keep a lock locked for long
            processing stages, call the refresh() method periodically
            (within the TTL time limit) on the lock object returned
            by this method.

        timeout

            The length of time (in seconds) to wait for the lock
            before giving up.  If this is 0, acquiring the lock is
            non-blocking, and the lock may not result in an acquired
            lock.  If this is greater than 0, attempts to acquire will
            give up after that number of seconds and may not result in
            an acquired lock.  If this is None attempts to acquire the
            lock will block indefinitely and are guaranteed to return
            an acquired lock.  To test whether the lock is acquired,
            use the is_aquired() method on the lock object returned by
            this method.

        """
        return LockHolder(self.etcd, self.name, ttl, timeout)
