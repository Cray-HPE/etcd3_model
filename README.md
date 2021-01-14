# ETCD3 Model Library

This library is supported under Python 3.x, it does not work with
Python 2.x.

The ETCD3 Models library allows the user to construct ETCD backed
"models" that can be used in an ETCD based persistent data store.
ETCD3 Models can be used in conjunction with Marshmallow schemas to
provide a rich and extensible serialization / deserialization
mechanism.  The declaration of the ETCD3 model itself simply defines
the named attributes and a few special characteristics of fields in
model instances (the individual objects within a model).

In addition to providing for persistence and class structuring of
data, ETCD3 Model also provides
- an object state mechanism to facilitate
managing the ojects in a Model / View / Controller pattern
application,
- an object watching mechanism that permits a process that
implements, for example, a View to update information in ETCD and a
process implementing, for example, a Controller to be alerted to that
change, and
- locking to protect against corruption of ETCD data as a
result of concurrent update by multiple replicas or by multiple parts
of an application.

This library is built on the 'etcd3' python module, which provides the
native operations needed to support the ETCD persistence, watching and
locking features.

# Creating Instantiating and Using an ETCD3 Model Class

## Creating

Creatng an ETCD3 Model class is simple.  First you need (somewhere in
your application) to set up an ETCD instance connection and make it
available everywhere you are going to define ETCD3 Models.  Let's say
you do this in a file called 'app.py':

```
from etcd3_model import create_instance

# Do the following once globally in your application and make the ETCD
# (or whatever you call it) variable available to all modules that
# define ETCD3 Model objects.
ETCD = create_instance()
```

The `create_instance()` function takes some information from environment
variable settings:

- ETCD_HOST specifies the hostname where the ETCD instance can be
found. Default is 'localhost'.

- ETCD_PORT specifies the port number on which the ETCD instance is
listening.  Default is 2379.

- ETCD_MOCK_CLIENT is a flag ('yes' or 'no') that tells etcd3_model
whether to use a real ETCD instance ('no') or a mocked ETCD instance
'yes') for its persistence.  This is here to support stand-alone
testing of ETCD based applications.

It then sets up a connection to your ETCD instance that you can use to
define model classes and persist data.

With this in place, here is a sample model class definition:

```
from .app import ETCD   # get the ETCD instance to use here
from etcd3_model import Etcd3Attr,Etcd3Model


class MyModel(Etcd3Model):
    """ Sample Model"""
    # The following provide the model with information about the ETCD
    # instance where the data are stored and the ETCD key space
    # prefix under which objects of this class will be stored.  They are
    # required as part of the model definition, and must have the names
    # given here.
    etcd_instance = ETCD
    model_prefix = "/testing/etcd3model/MyModel"

    # The name of the class instance attribute containing the Object
    # ID used to locate each instance.  You can pick any name to be on
    # the left hand side of the assignment.  On the right hand side is
    # an attribute definition.  In this case the attribute definition
    # has the distinction of being the Object ID attribute.  There
    # must be exactly one of these declarations per model.  The value
    # of this field will be assigned automatically by the ETCD3 Model
    # library.  By default a UUID string is used.  You may override
    # this by providing a callable object as the 'default' setting in
    # the attribute definition.  The only requirment is that the
    # function must produce unique IDs within the ETCD instance over
    # the life of the data.
    my_object_id = Etcd3Attr(is_object_id=True)

    # The following defines a set of fields.  The 'default'
    # characteristic may be either a constant of some kind or a
    # callable object.  Each field named here will exist in every
    # instance created using this model.  If the default value is
    # omitted, a value of None will be assigned at instance creation
    # time.
    stuff = Etcd3Attr(default="")
    more_stuff = Etcd3Attr(default="")
    even_more_stuff = Etcd3Attr(default=0)
```

## Instantiating an Object From a Model

There are two ways you can obtain an object using your model.  The
first creates the object fresh, ready to be interacted with and, when
you are ready, persisted.  The second retrieves an existing ETCD
object as an instance of its model.  We will look at each separately.

### Instantiating a New Object

Here is an example of code that instantiates a new instance of the
MyModel class above:

```
    my_instance = MyModel(stuff="here is some stuff",
                          more_stuff="here is some more stuff",
                          even_more_stuff=7)
```

What is returned from this is a not yet persisted instance of `MyModel`.
To persist the instance, do the following:

```
    my_instance.put()
```

When this returns, the instance is persisted and available to anyone
with access to the ETCD instance.

### Retrieving an Existing Model Instance

The following retrieves an object from ETCD as an instance of `MyModel`:

```
    retrieved = MyModel.get(my_instance.my_object_id)
```

It is important to note here that etcd3_model is not an ORM in the
sense that it does not bind all instances of the same data from ETCD
with each other.  Each time `MyModel.get(my_instance.my_object_id)` is
called, it creates a separate Python object with the same data in it.
Updating one will not update the others.

If your code has reason to believe that some other code may have
updated an object and stored the result back in ETCD, it can use
`MyModel.get()` to obtain the updated contents.  It will only see
contents that have been updated in ETCD using the `my_instance.put()`
method.

### Model Instance States

Each model instance has two attributes assigned to it by the ETCD3
Model library:

- `state`, and
- `messages`

The `state` attribute keeps track of the state of the object, which
can be one of the following:

- `READY`
- `UPDATING`,
- `DELETING`

While it is up to you application to move model instances through
these states, the library provides them and uses them internally.  An
object is considered `READY` when it has started in an `UPDATING` state
and run through any processing required to apply it to the system.  An
instance is `UPDATING` while it is still being processed by the
application.  An instance is `DELETING` when the application has decided
to delete the instance but is still processing any changes implied by
deleting the instance.  There is no `DELETED` state, because, in the
implied `DELETED` state the instance no longer exists.

The `messages` attribute is a list of messages that the application
has chosen to place with the instance that are relevant to the current
state the instance is in.  Messages are discarded at each state
transition.  Possible uses for messages are to record failures or
other conditions that might be preventing the instance from reaching
the next state from the current state, or to record progress toward
the next state.  For example, if deleting an instance entails deleting
a bunch of other entities, there may be messages showing each entity
being deleted.  There might also be message showing entities that
could not be deleted and are preventing deletion of the instance.

The messages mechanism differs from logging by the application in that
the messages are ephemeral.  Once the instance reaches, say, `READY`
from `UPDATING`, all of the messages stored while it was updating are
discarded.  Messages should be used to help clients understand the
current activites in the application, not to record the history of the
application.

### Watching An ETCD3 Model

An application can register to watch a given ETCD3 Model.  To do this,
the caller sets up a "watch queue" for the model as follows:

```
    my_queue = MyModel.watch()
```

The queue returned here will be filled with any objects that are
updated in ETCD while in the `UPDATING` or `DELETING` state as
long as the queue exists.  Objects that are deleted or enter the `READY`
state are not placed on the queue.  For example, suppose the View
portion of your application wants to change something in an instance
of `MyModel` and have the controller (watching on a queue) process that
change and update system state accordingly.  The View portion would do
the following:

```
    my_instance = MyModel.get(some_instance_id)
    my_instance.stuff = "new stuff"
    my_instance.state = UPDATING
    my_instance.put()
```

The controller, being the one who set up a watch queue above, would do
the following:

```
    instance = my_queue.get()
```

and receive the updated instance to process.

### Priming the Pump (learn)

When a consumer starts or restarts, it may need to trigger a sweep
through all of the instances in its model to make sure the system has
reached in the configured state.  Each model implements a `learn()`
method that facilitates this.  When `learn()` is called, every
instance in the model that is not in the `DELETING` state is placed in
the `UPDATING` state and touched, and every instance that is in the
`DELETING` state is touched and left in `DELETING` state.  This causes
watches to be triggered on every instance in the model, causing them
to flow down their queues to be processed.

Here is an example of a consumer calling `learn()` in a way that will
ensure that all instances will get a chance to flow to the consumer:

```
    # set up the queue so it is there to catch events...
    my_queue = MyModel.watch()
    # Trigger events
    MyModel.learn()
    ...
```

### Locking and Multiple Queues

There can be any number of queues watching the same model.  For
example, an application might have multiple replicas of a controller
processing updates.  To avoid corruption / collisions on processing a
change, only one controller wants to process each update.  To support
this, etcd3_model provides a locking mechanism at the instance data
level (i.e. shared across all instances with the same instance_id).

Locking uses ETCD's distributed locking mechanism which relies on a
time-to-live (TTL) to limit the amount of time a lock will be held if
the holder fails to release it for some reason (e.g. if the holder is
killed or crashes).  It is up to the application developer to ensure
that whatever needs to be done under lock is completed before the TTL
expires.

    NOTE: while the etcd3 library provides a refresh() method for
    locks, this is not currently provided by etcd3_model instances.
    Adding this adds a good deal of complexity to the mock etcd3
    library and, at present, no one has a use case that needs it.

The optimal processing model for incoming data on the queue is
multiple individual quick idempotent steps, each of which is followed
by `my_instance.put()` (or equivalent) doing one of the following:

- Leave the instance in the `UPDATING` or `DELETING` state with enough
information available for the next controller to move the process
forward,
- Move the instance to the `READY` state indicating that processing
is complete,
- Delete the instance.

This approach allows a given consumer of an update to fail or be
killed and restarted without causing the update to be lost.

Another thing to to keep in mind is that instances will arrive on all
consumers' queues in more or less the same order, meaning, typically,
at more or less the same time.  As a result, simple blocking attempts
to acquire the lock on each arriving instance tend to serialize all
consumers.  A better approach is to try to take the lock and skip the
instance if we can't get it (this means someone else has it).  To do
this, set the `timeout` value on acquiring the lock to 0
(non-blocking) and then check whether it is acquired before
proceeding.

The following illustrates an application implementing small
incremental steps with non-blocking lock acquisition:

```
    my_queue = MyModel.watch()
    MyModel.learn()  # Prime the watch queue in case we missed something
    while True:
        my_instance = my_queue.get()
        with my_instance.lock(ttl=60, timeout=0) as my_lock: # Non-blocking
            if not my_lock.is_acquired():
                # Someone else has the lock, skip this instance and
                # go back for more
                continue
            # I have the lock, process the instance...
            #
            # First, look it up again to make sure it still exists and
            # that we have the very latest data (now that we own the lock)
            safe_instance = MyModel.get(my_instance.my_object_id)
            if safe_instance is None or safe_instance.state == READY:
                # Someone else has either processed or deleted this instance,
                # we have nothing to do anymore.
                continue  # Go back for more work
            if safe_instance.state == DELETING:
                # There could be a processing sequence for this too, but for
                # simplicity let's just remove it.
                safe_instance.remove()
            elif not system.has_stuff(safe_instance.stuff):
                # The following should be a quick or asynchronous operation
                # to minimize blocking of other replicas.  Notice that the
                # timeout is shorter than the lock TTL, this permits failure
                # to release the lock and ensures we won't be in the
                # operation when the lock hits its TTL.
                system.set_stuff(safe_instance.stuff, timeout=50)
            elif not system.has_more_stuff(safe_instance.more_stuff):
                # See comment in previous block...
                system.set_more_stuff(safe_instance.more_stuff, timeout=50)
            elif not system.has_even_more_stuff(safe_instance.even_more_stuff):
                # See comment two blocks back...
                system.set_even_more_stuff(safe_instance.even_more_stuff,
                                           timeout=50)
            else:
                safe_instance.state = READY  # all done
        # Post the update outside of the lock to make sure that the update
        # gets queued with the lock released.  Otherwise all consumers
        # will race on the lock release and may drop the update.
        safe_instance.put()
            
```

Notice that the above processes an instance in `UPDATING` state in
discrete quick or asynchronous steps, resubmitting it, still in the
`UPDATING` state, for further processing at the end of each step.
Between steps, the instance is unlocked so other consumers can operate
on the instance.  This allows multiple replicas to safely cooperate on
driving configured state into a system without duplicating effort.

### Messages

If you want to record messages with each step of a process so that a
human can follow along and see what is happening (or where something
is stuck), you can add

```
            message = "What I just did was..."
```

in each of the processing stages above and then replace the

```
        safe_instance.put()
```

call above with

```
        safe_instance.post_message(message)
```

This will apply the specified message and do a `put()` operation
implicitly, so the update will still trigger a watch and be queued if
appropriate.

### More Stuff

The library is pretty heavily documented in docstrings, and there is
more there than shows up here, so feel free to poke around with help()
in python to see what you find.

# Standalone Application Testing

If you want to write unit tests for an application that uses
etcd3_model, you will want a stand-alone way to store, retrieve, watch
and so forth.  The etcd3_model can operate in a mocked ETCD instance
mode that permits you to do that.  By setting `ETCD_MOCK_CLIENT` to
'yes' in your environment before starting your application, you can
test it without the need for an external ETCD instance.

# Developer Notes

Please fee free to improve this code and submit pull requests.  When
you do, please follow a few basic rules.

## Observe Proper Semantic Versioning

Please update the version appropriately in etcd3_model/version.py to
reflect the new release version.

## Update this README as appropriate

This README is the introduction to important features of etcd3_model.
If you make a change that either changes the existing behavior or adds
new important behavior, consider documenting it here.

## Lint-Free and Style Clean Code

Lint or Style issues in the code of etcd3_model will break the build,
so please make sure all of the code you submit lints and passes style
checks.  Standalone linting is orchestrated by the `nox` framework.  If you don't have `nox` you can install it as follows:

```
$ pip3 install nox
```

Once you have nox, you can easily check for lint and style issues by
running:

```
$ nox -s lint && nox -s style
```

in the root directory of this repostory.

## Unit Test your Changes

### Mocking of the 'etcd3' Library

The etcd3_model is built around the 'etcd3' library and a
functional mock etcd3 library is provided under the
'etcd3_model/wrap_etcd3' directory.  This mock supports
both interface and simulation of etcd3 behavior to provide
a stand-alone implementation of all etcd3 features and
functions used by the etcd3_model library.  This allows
both etcd3 unit tests and applications built on the
etcd3_model library to run without the need for a real
ETCD instance.  When adding new functionality that draws
on previously unused aspects of 'etcd3', please extend
the functional and interface mocking so that your new
functionality is fully supported in a stand-alone mode.

### Unit Tests

Unit tests for the etcd3_model module are found in the 'tests'
sub-tree of this repository. Stand-alone testing is also available
under the `nox` framework.  The tests can be run as follows:

```
$ nox -s tests
```

Tests can be added either to the existing test files or simply by
adding a new '.py' file with a 'test_' prefix.  All test functions
are prefixed with 'test_' and should have reasonaby descriptive names.

The goal of testing of this module is 100% coverage with judicious use
of coverage pragmas to help in cases where test coverage does not make
sense or cannot be achieved.  The pragmas are defined and explained in
the .coveragerc file in this directory.  Choice of pragma is not
really critical, the various forms are meant to be a helpful way to
document the reason for the coverage exception. A build will pass with
95% coverage to allow you to develop and test without too much worry
about coverage. PRs with branch builds that don't reach 100% coverage,
however, will not be accepted.
