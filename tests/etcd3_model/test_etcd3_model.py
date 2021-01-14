"""
Python Tests for the ETCD Model Base Class

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
from time import sleep
from queue import Empty

from etcd3_model import (
    create_instance,
    Etcd3Attr,
    Etcd3Model,
    DELETING,
    UPDATING,
    READY
)
ETCD = create_instance()


def test_basic_etcd3_locking():
    """Make sure the underlying locking for etcd3 works as expected.  This
    is mostly here to test the mocking of using a raw etcd3 lock as a
    context manager because the etcd3_model code won't test that.

    """
    # Test that the lock works in a simple managed context.
    with ETCD.lock("foobar") as my_lock:
        assert my_lock.is_acquired()
    assert not my_lock.is_acquired()

    # Test that exceeding the TTL causes the lock to drop.
    with ETCD.lock("foo", ttl=1) as my_lock:
        sleep(2)
        assert not my_lock.is_acquired()
    assert not my_lock.is_acquired()


def test_basic_instantiation():
    """Create a basic Etcd3Model derived class instance using a legal
    class definition.

    """
    class MyModel(Etcd3Model):
        """ Test Model"""
        etcd_instance = ETCD
        model_prefix = "/testing/etcd3model/%s " % ("MyModel")

        # The Object ID used to locate each instance
        my_model_id = Etcd3Attr(is_object_id=True)

        # Some fields...
        stuff = Etcd3Attr(default="")
        more_stuff = Etcd3Attr(default="")
        even_more_stuff = Etcd3Attr(default=0)

    my_model = MyModel(stuff="here is some stuff",
                       more_stuff="here is some more stuff",
                       even_more_stuff="here is even more stuff")
    assert my_model.my_model_id
    assert my_model.stuff == "here is some stuff"
    assert my_model.more_stuff == "here is some more stuff"
    assert my_model.even_more_stuff == "here is even more stuff"
    assert my_model.get_id() == my_model.my_model_id

    # Store it to ETCD
    my_model.put()

    # Get it back again in a different instance and compare the
    # instances
    retrieved = MyModel.get(my_model.my_model_id)
    assert retrieved is not None
    assert retrieved.my_model_id == my_model.my_model_id
    assert retrieved.stuff == my_model.stuff
    assert retrieved.more_stuff == my_model.more_stuff
    assert retrieved.even_more_stuff == my_model.even_more_stuff
    assert retrieved.get_id() == my_model.my_model_id

    # Get all MyModel instances and make sure ours is (the only one)
    # there
    all_models = MyModel.get_all()
    assert isinstance(all_models, type([]))
    assert len(all_models) == 1
    retrieved = all_models[0]
    assert retrieved is not None
    assert retrieved.my_model_id == my_model.my_model_id
    assert retrieved.stuff == my_model.stuff
    assert retrieved.more_stuff == my_model.more_stuff
    assert retrieved.even_more_stuff == my_model.even_more_stuff

    # Post a message to it and make sure the message gets posted
    msg = "hello world!"
    my_model.post_message(msg)
    found = False
    for message in my_model.messages:
        if msg in message:
            found = True
    assert found
    retrieved = MyModel.get(my_model.my_model_id)
    found = False
    for message in retrieved.messages:
        if msg in message:
            found = True
    assert found

    # Post a one-time message several times and make sure it only
    # shows up once
    msg = "should only appear once"
    my_model.post_message_once(msg)
    my_model.post_message_once(msg)
    my_model.post_message_once(msg)
    my_model.post_message_once(msg)
    my_model.post_message_once(msg)
    found = 0
    for message in my_model.messages:
        if msg in message:
            found += 1
    assert found == 1
    retrieved = MyModel.get(my_model.my_model_id)
    found = 0
    for message in retrieved.messages:
        if msg in message:
            found += 1
    assert found == 1

    # Try some locking to make sure the locking mechanisms work
    with my_model.lock(ttl=2) as my_lock:
        assert my_lock.is_acquired()
        # Try a nested non-blockng lock and show that it cannot be acquired
        # and that it returns without locking.
        with my_model.lock(timeout=0) as my_second_lock:
            assert not my_second_lock.is_acquired()
        # Make sure adding the second lock didn't break the first one...
        assert my_lock.is_acquired()
    # Make sure coming out of the managed context, the lock is released
    assert not my_lock.is_acquired()

    # Try some more locking with ttl exhaustion this one is a bit
    # weird because the lock times out in the middle of the managed
    # context so it is not held at the end.
    with my_model.lock(ttl=2) as my_lock:
        assert my_lock.is_acquired()
        with my_model.lock(ttl=2) as my_second_lock:
            assert not my_lock.is_acquired()
            assert my_second_lock.is_acquired()
        assert not my_second_lock.is_acquired()
    assert not my_lock.is_acquired()

    # Set it to READY and make sure the messages go away and the state
    # goes to READY.  Do this under lock to test locking as well...
    my_model.set_ready()
    assert my_model.state == READY
    assert my_model.messages == []
    retrieved = MyModel.get(my_model.my_model_id)
    assert retrieved.state == READY
    assert retrieved.messages == []

    # Delete it and make sure its state goes to DELETING
    msg = "Goodbye cruel world"
    my_model.delete(msg)
    assert my_model.state == DELETING
    retrieved = MyModel.get(my_model.my_model_id)
    assert retrieved.state == DELETING
    found = False
    for message in retrieved.messages:
        if msg in message:
            found = True
    assert found

    # Remove it and make sure it is gone
    my_model.remove()
    retrieved = MyModel.get(my_model.my_model_id)
    assert retrieved is None

    # And, for good measure, make sure it doesn't show up in the list
    # either
    all_models = MyModel.get_all()
    assert isinstance(all_models, type([]))
    assert all_models == []


# pylint: disable=redefined-outer-name
def test_field_defaults():
    """Test defining a model with a non-standard object id generator and
    show that the generator generates the expected sequence of
    object-ids.

    """
    class MyModel(Etcd3Model):
        """ Test Model"""
        etcd_instance = ETCD
        model_prefix = "/testing/etcd3model/%s " % ("MyModel")

        # The Object ID used to locate each instance
        my_model_id = Etcd3Attr(is_object_id=True)

        # Some fields...
        stuff = Etcd3Attr(default="default stuff")
        more_stuff = Etcd3Attr(default="more default stuff")
        even_more_stuff = Etcd3Attr(default="even more default stuff")

    my_model = MyModel()
    assert my_model.my_model_id
    assert my_model.stuff == "default stuff"
    assert my_model.more_stuff == "more default stuff"
    assert my_model.even_more_stuff == "even more default stuff"


# pylint: disable=redefined-outer-name
def test_object_id_default():
    """Test defining a model with a non-standard object id generator and
    show that the generator generates the expected sequence of
    object-ids.

    """
    next_obj_id = 0

    def object_id_gen():
        """ Example non-default object-id generator.
        """
        nonlocal next_obj_id
        ret = next_obj_id
        next_obj_id += 1
        return ret

    class MyModel(Etcd3Model):
        """ Test Model"""
        etcd_instance = ETCD
        model_prefix = "/testing/etcd3model/%s " % ("MyModel")

        # The Object ID used to locate each instance
        my_model_id = Etcd3Attr(is_object_id=True, default=object_id_gen)

        # Some fields...
        stuff = Etcd3Attr(default="")
        more_stuff = Etcd3Attr(default="")
        even_more_stuff = Etcd3Attr(default=0)

    for i in range(0, 10):
        my_model = MyModel(stuff="here is some stuff",
                           more_stuff="here is some more stuff",
                           even_more_stuff="here is even more stuff")
        assert my_model.my_model_id == i


# pylint: disable=redefined-outer-name
def test_watch_and_learn():
    """Test watching and learning of ETCD model objects.  Verify that
    watching an object of a given type causes put events to flow down
    the queue associated with the object class but not down any queue
    associated with another object class.  Also show that delete
    events are ignored as are put events on READY objects.  Finally,
    show that the 'learn' method on a class causes all objects of that
    class to show up on the queue.

    """
    class MyWatchModel(Etcd3Model):
        """ Test Model"""
        etcd_instance = ETCD
        model_prefix = "/testing/etcd3model/%s" % ("MyWatchModel")

        # The Object ID used to locate each instance
        my_model_id = Etcd3Attr(is_object_id=True)

    class MyOtherModel(Etcd3Model):
        """ Test Model"""
        etcd_instance = ETCD
        model_prefix = "/testing/etcd3model/%s" % ("MyOtherModel")

        # The Object ID used to locate each instance
        my_model_id = Etcd3Attr(is_object_id=True)

    # Set up watching on MyWatchModel()
    queue = MyWatchModel.watch()
    second_queue = MyWatchModel.watch()
    # Create a bunch of MyWatchModel instances
    instances = [MyWatchModel() for i in range(0, 5)]

    # Actually put the new objects into ETCD, they should flow down
    # 'queue' as they are created.
    for instance in instances:
        instance.put()

    # Set up watching on MyOtherModel
    other_queue = MyOtherModel.watch()
    # Create a bunch of MyOtherModel instances, these should flow down
    # 'other_queue' as they are created.
    other_instances = [MyOtherModel() for i in range(0, 5)]

    # Actually put the new objects into ETCD, they should flow down
    # 'other_queue' as they are created.
    for instance in other_instances:
        instance.put()

    # Check that all of the MyWatchModel instances flowed down 'queue'
    # exactly once and that nothing unexpected flowed down 'queue'
    done = False
    instance_ids = [instance.my_model_id for instance in instances]
    while not done:
        try:
            observed = queue.get_nowait()
            assert isinstance(observed, MyWatchModel)
            assert observed.my_model_id in instance_ids
            instance_ids.remove(observed.my_model_id)
        except Empty:
            done = True
    assert instance_ids == []

    # Check that all of the MyWatchModel instances also flowed down
    # 'second_queue' exactly once and that nothing unexpected flowed
    # down 'second_queue'
    done = False
    instance_ids = [instance.my_model_id for instance in instances]
    while not done:
        try:
            observed = second_queue.get_nowait()
            assert isinstance(observed, MyWatchModel)
            assert observed.my_model_id in instance_ids
            instance_ids.remove(observed.my_model_id)
        except Empty:
            done = True
    assert instance_ids == []

    # Check that all of the MyOtherModel instances flowed down
    # 'other_queue' exactly once and that nothing unexpected flowed
    # down 'other_queue'
    done = False
    instance_ids = [instance.my_model_id for instance in other_instances]
    while not done:
        try:
            observed = other_queue.get_nowait()
            assert isinstance(observed, MyOtherModel)
            assert observed.my_model_id in instance_ids
            instance_ids.remove(observed.my_model_id)
        except Empty:
            done = True
    assert instance_ids == []

    # Set all of the MyWatchModel instances to the READY state, and show
    # that 'queue' remains quiet.
    for instance in instances:
        instance.state = READY
        instance.put()
    assert queue.empty()

    # Remove all of the MyOtherModel instances and show that
    # 'other_queue' remains quiet.
    for instance in other_instances:
        instance.remove()
    assert other_queue.empty()

    # Now, try to 'learn' all of the MyWatchModel instances and verify that
    # they all come down the queue.
    #
    # Gather the instance ids again...
    instance_ids = [instance.my_model_id for instance in instances]

    # Kick off the learn...
    MyWatchModel.learn()
    # Check that all of the MyWatchModel instances flowed down 'queue'
    # exactly once and that nothing unexpected flowed down 'queue'
    done = False
    while not done:
        try:
            observed = queue.get_nowait()
            assert isinstance(observed, MyWatchModel)
            assert observed.state in [UPDATING, DELETING]
            assert observed.my_model_id in instance_ids
            instance_ids.remove(observed.my_model_id)
        except Empty:
            done = True
    assert instance_ids == []


# pylint: disable=redefined-outer-name,unused-argument
def test_bad_object_id_default():
    """Test defining a model with a non-callable object id generator
    and show that instantiation fails as expected.

    """
    try:
        class MyModel(Etcd3Model):
            """ Test Model"""
            # The Object ID used to locate each instance
            my_model_id = Etcd3Attr(is_object_id=True,
                                    default="fixed string(bad)")
        # If this is working right, it will cause an exception which
        # will prevent it from being counted in the coverage report,
        # hence the pragma.
        MyModel(stuff="here is some stuff",        # pragma no cover
                more_stuff="here is some more stuff",
                even_more_stuff="here is even more stuff")
    except ValueError as exc:
        assert "'default' for Object ID is not callable" in str(exc)
    # We really want to catch all exceptions here and fail if we get
    # one.
    #
    # pylint: disable=broad-except
    except Exception:  # pragma unit test failure
        assert False
    else:  # pragma unit test failure
        assert False


# pylint: disable=redefined-outer-name
def test_missing_object_id():
    """Test instantiating a model that has no object id field.  Should
    get an AttributeError exception and a specific string

    """
    class MyModel(Etcd3Model):
        """ Test Model"""
        etcd_instance = ETCD
        model_prefix = "/testing/etcd3model/%s " % ("MyModel")

        # Some fields...
        stuff = Etcd3Attr(default="")
        more_stuff = Etcd3Attr(default="")
        even_more_stuff = Etcd3Attr(default=0)

    try:
        MyModel(stuff="here is some stuff",
                more_stuff="here is some more stuff",
                even_more_stuff="here is even more stuff")
    except AttributeError as exc:
        assert "must have an Object ID in" in str(exc)
    # We really want to catch all exceptions here and fail if we get
    # one.
    #
    # pylint: disable=broad-except
    except Exception:  # pragma unit test failure
        assert False
    else:  # pragma unit test failure
        assert False


# pylint: disable=redefined-outer-name
def test_two_object_ids():
    """Test instantiating a model with two different object id fields.
    Should get an AssertionError with a specific string.

  """
    class MyModel(Etcd3Model):
        """ Test Model"""
        etcd_instance = ETCD
        model_prefix = "/testing/etcd3model/%s " % ("MyModel")

        # The Object ID used to locate each instance
        my_model_id = Etcd3Attr(is_object_id=True)

        # Another Object ID used to locate each instance (bad)
        my_other_model_id = Etcd3Attr(is_object_id=True)

        # Some fields...
        stuff = Etcd3Attr(default="")
        more_stuff = Etcd3Attr(default="")
        even_more_stuff = Etcd3Attr(default=0)
    try:
        MyModel(stuff="here is some stuff",
                more_stuff="here is some more stuff",
                even_more_stuff="here is even more stuff")
    except AssertionError as exc:
        assert "can't have two Object IDs in" in str(exc)
    # We really want to catch all exceptions here and fail if we get
    # one.
    #
    # pylint: disable=broad-except
    except Exception:  # pragma unit test failure
        assert False
    else:  # pragma unit test failure
        assert False


# pylint: disable=redefined-outer-name,unused-argument
def test_missing_etcd_instance():
    """Test instantiating a model without an 'etcd_instance' specified
    Should get an AttributeError with a specific string.

  """
    class MyModel(Etcd3Model):
        """ Test Model"""
        model_prefix = "/testing/etcd3model/%s " % ("MyModel")

        # The Object ID used to locate each instance
        my_model_id = Etcd3Attr(is_object_id=True)

        # Some fields...
        stuff = Etcd3Attr(default="")
        more_stuff = Etcd3Attr(default="")
        even_more_stuff = Etcd3Attr(default=0)
    try:
        MyModel(stuff="here is some stuff",
                more_stuff="here is some more stuff",
                even_more_stuff="here is even more stuff")
    except AttributeError as exc:
        assert "missing required attribute 'etcd_instance'" in str(exc)
    # We really want to catch all exceptions here and fail if we get
    # one.
    #
    # pylint: disable=broad-except
    except Exception:  # pragma unit test failure
        assert False
    else:  # pragma unit test failure
        assert False


# pylint: disable=redefined-outer-name
def test_missing_model_prefix():
    """Test instantiating a model without a 'model_prefix' specified
    Should get an AttributeError with a specific string.

  """
    class MyModel(Etcd3Model):
        """ Test Model"""
        etcd_instance = ETCD

        # The Object ID used to locate each instance
        my_model_id = Etcd3Attr(is_object_id=True)

        # Some fields...
        stuff = Etcd3Attr(default="")
        more_stuff = Etcd3Attr(default="")
        even_more_stuff = Etcd3Attr(default=0)
    try:
        MyModel(stuff="here is some stuff",
                more_stuff="here is some more stuff",
                even_more_stuff="here is even more stuff")
    except AttributeError as exc:
        assert "missing required attribute 'model_prefix'" in str(exc)
    # We really want to catch all exceptions here and fail if we get
    # one.
    #
    # pylint: disable=broad-except
    except Exception:  # pragma unit test failure
        assert False
    else:  # pragma unit test failure
        assert False
