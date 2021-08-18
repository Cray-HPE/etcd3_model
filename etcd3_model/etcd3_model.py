"""
Object Storage Support for ETCD Version 3

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
import uuid
import json
import inspect
import copy
from queue import Queue as SimpleQueue
from .utils import clean_desc
from .lockable import Lockable
from .wrap_etcd3 import PutEvent

# State constants
READY = 'READY'
UPDATING = 'UPDATING'
DELETING = 'DELETING'

STATE_DESCRIPTION = clean_desc("""
The state of an object vis-a-vis the configuration.
Values are: 'READY', 'UPDATING', 'DELETING', 'DELETED',
'PENDING'.  The 'READY' state means the configuration has been
absorbed and propagated and the object is reconciled as
configured.  The 'UPDATING' state means the configuration has
changed and the changes are still being absorbed and
propagated.  The 'DELETING' state means deletion of the object
has been requested and is being processed but is not complete
yet. The 'DELETED' state means all resources associated with
the object configuration have been cleaned up and the object
no longer exists. The configuration can safely be removed.
The 'PENDING' state means some condition that requires manual
intervention has prevented the object from reaching the
'READY' state from the 'UPDATING' or 'CREATED' state.
A newly created object starts in the 'UPDATING' state.
""")

MESSAGES_DESCRIPTION = clean_desc("""
In conjunction with 'state' there may be messages that
describe either an object's progress toward 'READY' or
'DELETED' states or reasons for reaching the 'PENDING'
state.  The 'messages' field provides these in a list of
strings.""")


class Etcd3Attr:
    """Etcd3 Attribute Specification

    Each instance attribute of a derived model class is described in
    the derived class by a class attribute of the same name that is
    assigned a value of the type Etcd3Attr.  In its simplest form, an
    instance attribute specification looks like the following:

        class MyModel(Etcd3Model):
            my_attribute = Etcd3Attr(default="nothing to see here")
            ...

    It is also possible to specify additional characteristics of the
    instance attribute.  For example, if the instance attribute takes
    a default value or has a callable object that provides a default
    value, that can be specified using the following form:

        class MyModel(Etcd3Model):
            my_attribute = Etcd3Attr(default="nothing to see here")
            ...

    The (required) instance attribute that contains the Object ID used
    to store and retrieve the instance from ETCD is identified by a
    specification like:

         class MyModel(Etcd3Model):
            my_model_id = Etcd3Attr(is_object_id=True)
            ...

    Optionally, a non-default Object ID calculation could be specified
    for this instance attribute as follows:

         class MyModel(Etcd3Model):
            my_model_id = Etcd3Attr(is_object_id=True, default=my_objid_func)
            ...

    Only one instance attribute can be the Object ID and the default
    Object ID function produces a UUID string.  If an alternative
    identifier function is used, it must produce an Object ID that is
    (at least) unique within the space of instances of the derived
    model.

    Any attribute except for the one tagged as the Object ID that does
    not specify a 'default' setting is assigned a value of None if it
    is not specified at instance creation time.

    """
    @staticmethod
    def _default_object_id():
        """ Return a UUID string to use as a default style object-id
        """
        return str(uuid.uuid4())

    def __init__(self, is_object_id=False, default=None):
        """Construct an attribute specification

        Parameters:

            is_object_id:

                 If set to True indicates that this attribute contains
                 the Object ID for the instance.  Default value is
                 False.  Only one instance attribute may contain the
                 Object ID.

             default:

                 If set, declares either the default value to be
                 assigned if the attribute value is not supplied at
                 instance creation time, or a callable object
                 (e.g. function) to be called to obtain that default
                 value.

        """
        if is_object_id:
            if default is not None and not callable(default):
                raise ValueError("'default' for Object ID is not callable")
            if default is None:
                default = Etcd3Attr._default_object_id
        self.default = default
        self.is_object_id = is_object_id

    def get_default_value(self):
        """Obtain the default value for a field (either by calling a callable
        or by simply returning the value depending on the type of the
        default setting.

        """
        default = self.default
        if callable(default):
            return default()
        # For any non-callable, make sure that we are not
        # replicating the same object, list, dictionary, or
        # whatever across all objects of this type by using what
        # is there as a template, but not the actual thing.  A
        # little bit of overhead for scalars, but safer for all
        # concerned.
        default = copy.deepcopy(default)
        return default


class Etcd3Model(Lockable):
    """Etcd3 Model

    This implements a parent class for ETCD version 3 Model classes
    which takes care of retrieving data from ETCD and storing data in
    an ETCD instance using a schema that encapsulates all of the
    derived class data as a JSON string referenced by a prefix that
    groups objects of the same class and an Object ID to indicate the
    specific instance.

    A derived model class must declare all of the instance attributes
    (see the Etcd3Attr class for details).  Any parameter passed into
    the initializer whose name is not in the list of declared instance
    attributes is silently ignored.  One of these instance attributes
    must be identified as the Object ID for instances of the derived
    model class.

    In addition to the instance attributes, The ETCD instance for a
    derived model must be provided as a class variable in the derived
    class.  This takes the form:

        class MyModel(Etcd3Model):
            etcd_instance = project_etcd_client
            ...

    where 'project_etcd_client' is whatever ETCD client connection you
    have set up for the project at initialization.

    Within the ETCD instance, the form of a key is:

        /<Base Prefix>/<Model Name>/<Object ID>

    Where the Base Prefix is a project specific prefix string that
    isolates the project models from those of other projects, the
    Model Name is the name of the derived model class, and the Object
    ID is the ID of a single derived model instance.  An example for
    the project "my_project" and a model within that project
    "my_model" and an Object ID

        89e50500-f3b6-4818-982d-cc589dea8be5

    might be:

        /projects/my_project/my_model/89e50500-f3b6-4818-982d-cc589dea8be5

    In this case the Base Prefix is "/projects/my_project", the Model
    Name is "my_model" and the Object ID is

        89e50500-f3b6-4818-982d-cc589dea8be5

    The model prefix (e.g. "/projects/my_project/my_model") must be
    provided as a class variable in the derived class.  This takes the
    form:

        class MyModel(Etcd3Model):
            model_prefix = "%s/%s" % (base_prefix, 'MyModel')
            ...

     where 'base_prefix' is a project specific base prefix of your
     choice and 'MyModel' is the Model Name under the Base Prefix.
     The 'model_prefix' setting is then used for composing key names.

    There is a pair of Model Attributes that are provided by the base
    Etcd3Model class so that all derived classes can use them:

        state

    and

        messages

    The value of 'state' is used to track the state of an ETCD3 object
    as it moves through controller logic from creation to realization
    on the system or from deletion to removal from the system.  The
    states recognized are:

    READY

        The object is fully realized in the system with its current
        contents and is in the operational steady state.  On
        transition to READY, all messages are cleared from 'messages'.

    UPDATING

        The object is newly created or newly changed and its
        controller(s) need to realize it in the system.  If a problem
        that seems to require external intervention arises while an
        object is in the UPDATING state, a message describing the
        problem will be posted in 'messages' and the object will
        remain in UPDATING.  Once the object has been realized, it
        will transition to READY.  If the object is deleted while in
        UPDATING, it will transition to DELETING.

    DELETING

        A client has requested that the object be deleted from the
        system and the object's controller(s) need to remove the
        corresponding state from the system and then mark the object
        as deleted.  If a problem that seems to require external
        intervention arises while an object is in DELETING state, a
        message describing the problem will be posted in 'messages'
        and the object will remain in DELETING.  Once the system state
        associated with the object has been removed, the controller
        should remove the object from ETCD using the remove() method.

    The value of 'messages' is a list of messages describing the
    current status of a state transition, including, but not limited
    to those describing the need for external intervention.  Each time
    a new message is posted in 'messages', watchers (controllers, for
    example) of the object will be sent a new instance of the object
    to reconcile.

    """
    # Set up 'state' and 'messages'
    state = Etcd3Attr(default=UPDATING)
    messages = Etcd3Attr(default=[])

    @classmethod
    def post_event(cls, event):
        """Respond to 'event' (which is an ETCD watch event) by either
        discarding it (if it is a DeleteEvent or a PutEvent for an
        object in the READY state) or constructing an object of the
        type specified in 'cls' and sending it down all of the watch
        queues for that type.

        """
        obj = None
        if isinstance(event, PutEvent):
            # The object was modified, pack up a new object of the
            # specified class with the new value and put it on the
            # queue
            json_string = event.value.decode('utf-8')
            class_dict = json.loads(json_string)
            obj = cls(class_dict)
        else:
            # For the time being, we don't care about DeleteEvents
            # because the controllers will initiate all of them.  To
            # cut down on unwanted event traffic to the controllers,
            # and to keep the controllers simple, just toss anything
            # that is not a PutEvent
            return
        # Objects that are in the READY state do not need to be sent
        # down the watch queues.  Any object that contains an update
        # or deletion request will be marked UPDATING or or DELETING.
        # READY is the state it arrives in when it finishes UPDATING.
        # So, keep the traffic lower by tossing READY objects here.
        if obj.state == READY:
            return

        # Should not be able to get here without having defined
        # 'watch_queues' in 'cls', but to be safe, we don't really
        # care if this gets called before there are any queues, we can
        # just drop the event on the floor.
        try:
            for queue in cls.watch_queues:
                queue.put(obj)
        except AttributeError:  # pragma no cover
            # No big deal, no watch_queues yet, so nothing to do.
            pass

    @classmethod
    def get(cls, object_id):
        """Find an instance of the specified model in ETCD with the model
        prefix specified in the 'model_prefix' attribute of the model
        and the specified Object ID.

        Parameters:

            cls:
                The class of the model to query (implicit if this
                is called as MyModel.get(object_id).

            object_id:
               The Object ID of the target instance

        Return:

             A python object of type 'cls' containing what was found
             in ETCD if 'object_id' exists in ETCD.

             None if 'object_id' does not exist in ETCD.

        Example:
            If the class name of your model is 'MyModel' and the object id
            of the instance you want to get from ETCD is:

                89e50500-f3b6-4818-982d-cc589dea8be5

            you would call this as:

                my_model = MyModel.get('89e50500-f3b6-4818-982d-cc589dea8be5')

        """
        etcd = cls.etcd_instance  # pylint: disable=no-member
        # pylint: disable=no-member
        key = "%s/%s" % (cls.model_prefix, object_id)
        json_data, _ = etcd.get(key)
        if json_data is None:
            return None
        json_string = json_data.decode('utf-8')
        class_dict = json.loads(json_string)
        return cls(class_dict)

    @classmethod
    def get_all(cls):
        """Find all instances of the specified model in ETCD with the model
        prefix specified by the 'model_prefix' attribute of the model.

        Parameters:

            cls:
                The class of the model to query (implicit if this
                is called as MyModel.get(object_id).

        Returns:

            A list of model objects of the derived class.
        """
        etcd = cls.etcd_instance  # pylint: disable=no-member
        prefix = cls.model_prefix + '/'  # pylint: disable=no-member
        objects = etcd.get_prefix(prefix)
        ret = []
        for obj in objects:
            json_string = obj[0].decode('utf-8')
            class_dict = json.loads(json_string)
            ret += [cls(class_dict)]
        return ret

    @classmethod
    def watch(cls):
        """Create a watch queue to watch for ETCD events on objects in the
        derived class 'cls'.  All events on ETCD KVs with the model
        prefix will be delivered on the queue.

        NOTE: this is not thread-safe. It assumes that the callers of
              watch() are all in one overall controller thread.  At
              the time this was written, this assumption was valid.
              If that changes this function will need to change to use
              locking to avoid race conditions that could cause event
              queues to be lost.

        """
        new_queue = SimpleQueue()
        try:
            cls.watch_queues.append(new_queue)
            return new_queue
        except AttributeError:
            # We haven't set up for watch queues yet.  Since the above
            # will return if it works, the rest of this function is
            # effectively the exception case, just pass here so we
            # can get out of exception handling.
            pass

        # First off, we need a list for watch queues, and we might as
        # well put the queue we have in it right away.
        cls.watch_queues = [new_queue]

        # Set up a watch range that covers all of the items that fit in:
        #
        #      <model_prefix>/<item>
        #
        # This is done by adding a '/' to the prefix for the start and
        # adding the character one past '/' for the end.  All keys we
        # want will fall in that range of strings.
        start = cls.model_prefix + '/'  # pylint: disable=no-member
        end = cls.model_prefix + chr(ord('/') + 1)  # pylint: disable=no-member

        # Set up the watch callback.  Hang onto the watch ID we get for it
        # so we can cancel it later if we want to for some reason.
        #
        # pylint: disable=no-member
        cls.watch_id = cls.etcd_instance.add_watch_callback(start,
                                                            cls.post_event,
                                                            range_end=end)
        return new_queue

    @classmethod
    def learn(cls):
        """Start the flow of information into the watchers for every object
        in a given class by posting a 'learning' message into the
        object.

        """
        objects = cls.get_all()
        for obj in objects:
            if obj.state != DELETING:
                # All objects being learned are UPDATING unless they
                # are DELETING.  They will be READY (or gone) after
                # they have been learned.
                obj.state = UPDATING
            obj.post_message("Learning initiated")

    def _get_instance_attrs(self):
        """Build a dictionary of instance attributes and their respective
        specifications.

        """
        ret = {}
        members = inspect.getmembers(type(self))
        for member in members:
            if isinstance(member[1], Etcd3Attr):
                ret[member[0]] = member[1]
        return ret

    def _get_object_id_info(self):
        """Find the name of the field specified to contain the Object ID in
        instances of the derived model class (if any).

        Returns:
            A tuple containing the name of the field and the
            attribute specification associated with that name.

        Exceptions:

            If more than instance attribute is tagged as the Object ID
            in the derived class, an AssertionError exception is
            raised.

            If no instance attribute is tagged as the Object ID
            in the derived class, an AttributeError exception is
            raised.

        """
        ret = None
        attrs = self._get_instance_attrs()
        for attr, spec in attrs.items():
            if spec.is_object_id:
                if ret is not None:
                    # pylint: disable=invalid-name
                    t = str(type(self))
                    reason = "can't have two Object IDs in '%s'" % t
                    raise AssertionError(reason)
                ret = (attr, spec)
        if ret is None:
            # pylint: disable=invalid-name
            t = str(type(self))
            reason = "must have an Object ID in '%s'" % t
            raise AttributeError(reason)
        return ret

    def __init__(self, *args, **kwargs):
        """Initializer -- construct a model from keyword arguments or a
        dictionary of key value pairs.
        """
        # Make sure that all of the required pieces are specified as
        # class attributes in the derived class we are constructing.
        # Raise an AttributeError if any are missing.
        for name in ['etcd_instance', 'model_prefix']:
            if name not in type(self).__dict__:
                # pylint: disable=invalid-name
                t = str(type(self))
                reason = "'%s' missing required attribute '%s'" % (t, name)
                raise AttributeError(reason)

        # Make sure there is an object-id field specified (the call
        # will exception if none is present).  Ignore the return.
        self._get_object_id_info()

        # Get the declared instance attribute specifications for use
        # in validating input and in filling out defaults.
        attr_specs = self._get_instance_attrs()

        # Pick up any dictionary arguments provided with the call and
        # absorb any key / value pairs found there.
        for arg_dict in args:
            for attr, value in arg_dict.items():
                # Only take key / value pairs that are recognized,
                # drop others silently.
                if attr in attr_specs:
                    setattr(self, attr, value)

        # Pick up any settings that came in as keyword args
        for attr, value in kwargs.items():
            # Only take key / value pairs that are recognized,
            # drop others silently.
            if attr in attr_specs:
                setattr(self, attr, value)

        # Now run through the list of instance attributes and create
        # any that were not specified in the call.  This will also
        # take care of setting the Object ID if no Object ID attribute
        # was specified in the call, since one of the instance
        # attributes has to be the Object ID.
        for attr, spec in attr_specs.items():
            if attr not in self.__dict__:
                setattr(self, attr, spec.get_default_value())

        # Set up the locking for the instance, now that we know the
        # etcd instance, prefix and object id of the instance.
        model_prefix = type(self).__dict__['model_prefix']
        etcd_instance = type(self).__dict__['etcd_instance']
        name = "%s/%s" % (model_prefix, str(self.get_id()))
        Lockable.__init__(self, name, etcd_instance)

    def get_id(self):
        """ Get the object id (key) of an object
        """
        oid_name, _ = self._get_object_id_info()
        return self.__dict__[oid_name]

    def delete(self, message=None):
        """Set the object state to DELETING with an optional message which
        will be put in 'messages' and update it in ETCD.

        """
        if message:
            assert isinstance(message, str)  # disallow non-string messages
            self.messages.append(message)  # pylint: disable=no-member
        self.state = DELETING
        self.put()

    def post_message(self, message):
        """Post a caller supplied message in the 'messages' list of the
        object and update the object in ETCD.

        """
        assert isinstance(message, str)  # disallow non-string messages
        assert message  # Disallow empty messages
        self.messages.append(message)  # pylint: disable=no-member
        self.put()

    def post_message_once(self, message):
        """Post a caller supplied message in the 'messages' list of the object
        if the message is not already there then unconditionally
        update the object in ETCD to ensure a watch event.

        """
        assert isinstance(message, str)  # disallow non-string messages
        assert message  # Disallow empty messages
        for msg in self.messages:
            if message in msg:
                # Already have it, just update and return
                self.put()
                return
        self.messages.append(message)  # pylint: disable=no-member
        self.put()

    def put(self):
        """ Store the object to ETCD in its current state.
        """
        oid_name, _ = self._get_object_id_info()
        object_id = self.__dict__[oid_name]
        etcd = type(self).etcd_instance  # pylint: disable=no-member
        # pylint: disable=no-member
        key = "%s/%s" % (type(self).model_prefix, object_id)
        # Compose the JSON string to be stored for this model.  Only
        # include in the JSON string the fields that are declared in
        # the model attribute specification.  Any other fields that
        # might exist are treated as ephemeral.  This allows us to
        # keep track of and report run-time information in schemas
        # built on this model without having to persist run-time data.
        put_dict = {}
        attr_specs = self._get_instance_attrs()
        for attr, spec in self.__dict__.items():
            if attr in attr_specs:
                put_dict[attr] = spec
        json_string = json.dumps(put_dict)
        etcd.put(key, json_string)

    def set_ready(self):
        """Transition to a READY state which clears any messages and sets
        state to READY.

        """
        self.messages = []
        self.state = READY
        self.put()

    def remove(self):
        """ Remove the ETCD instance from the key value store.
        """
        oid_name, _ = self._get_object_id_info()
        object_id = self.__dict__[oid_name]
        etcd = type(self).etcd_instance  # pylint: disable=no-member
        # pylint: disable=no-member
        key = "%s/%s" % (type(self).model_prefix, object_id)
        etcd.delete(key)
