import logging
import pykka


logger = logging.getLogger(__name__)


class ServiceErrors():
    SUCCESS = 0
    MESSAGE_DIRECTION_INCORRECT = 1
    RESOURCE_DOES_NOT_EXIST = 2
    CONTEXT_DOES_NOT_EXIST = 3
    JSON_ENCODING_ERROR = 4
    JSON_SCHEMA_VALIDATION_ERROR = 5
    RESOURCE_CANNOT_BE_DELETE = 6
    METHOD_NOT_IMPLEMENTED = 7
    METHOD_NOT_SUPPORTED_ON_OBJECT = 8
    ILLEGAL_STATE = 9
    UNRECOGNISED_STATE = 10
    MALFORMED_DATA_OBJECT = 11
    RESOURCE_EXCEPTION = 12


class ServiceException(Exception):
    pass


class ServiceSuccess():
    error_code = ServiceErrors.SUCCESS
    message = 'Success'


class ServiceMalformedDataObject(ServiceException):
    error_code = ServiceErrors.MALFORMED_DATA_OBJECT
    message = 'The supplied data object is not valid for this resource'


class ServiceIllegalState(ServiceException):
    error_code = ServiceErrors.ILLEGAL_STATE
    message = 'The state requested is illegal in the current state'


class ServiceUnrecognisedState(ServiceException):
    error_code = ServiceErrors.UNRECOGNISED_STATE
    message = 'The state requested is not a recognised allowed state'


class ServiceMethodNotImplemented(ServiceException):
    error_code = ServiceErrors.METHOD_NOT_IMPLEMENTED
    message = 'The requested method is not implemented on this object'


class ServiceResourceCannotBeDeletedError(ServiceException):
    error_code = ServiceErrors.RESOURCE_CANNOT_BE_DELETE
    message = 'The requested resource cannot be deleted'


class ServiceResourceDoesNotExist(ServiceException):
    error_code = ServiceErrors.RESOURCE_DOES_NOT_EXIST
    message = 'Resource path does not exist'


class ServiceResourceException(ServiceException):
    error_code = ServiceErrors.RESOURCE_EXCEPTION
    message = 'Resource specific exception raised'
    def __init__(self, message):
        super().__init__()
        self.message = message


class ServiceResource(pykka.ThreadingActor):

    def __init__(self, path):
        """Override method to add own behaviours"""
        pykka.ThreadingActor.__init__(self)
        self._path = path
        self._proxy = self.actor_ref.proxy()
        ServiceResourceRegistry.register(self._proxy, path)

    def on_stop(self):
        logger.debug('[%s] stopping', self._path)
        ServiceStateChangeRegistry.unregister_all(self._proxy)
        ServiceResourceRegistry.unregister(self._proxy, self._path)

    def notify(self, path, state):
        """Implemented by child"""
        raise ServiceMethodNotImplemented

    def set_state(self, state):
        """Implemented by child"""
        raise ServiceMethodNotImplemented

    def get_state(self):
        """Implemented by child"""
        raise ServiceMethodNotImplemented

    def delete(self):
        """Implemented by child"""
        raise ServiceMethodNotImplemented


class ServiceResourceRegistry():
    __registry = {}

    @classmethod
    def register(cls, obj, resource):
        if resource in cls.__registry:
            raise ServiceException('Resource path conflict - {} already exists'.format(resource))
        cls.__registry[resource] = obj

    @classmethod
    def unregister(cls, obj, resource=None):
        if resource:
            cls.__registry.pop(resource, None)
        else:
            for r in cls.__registry:
                if cls.__registry[r] == obj:
                    cls.__registry.pop(r, None)

    @classmethod
    def set_resource(cls, resource, data):
        objs = cls._lookup(resource)
        if not objs:
            raise ServiceResourceDoesNotExist
        for (path, obj) in objs:
            if path:
                z = data
                for i in path:
                    if i in z:
                        z = z[i]
                    else:
                        z = None
                        break
                if z:
                    obj.set_state(z)
            else:
                obj.set_state(data).get()

    @classmethod
    def delete_resources(cls, resources):
        for r in resources:
            if r not in cls.__registry:
                raise ServiceResourceDoesNotExist
        for r in resources:
            if r in cls.__registry:
                obj = cls.__registry[r]
                obj.delete().get()

    @classmethod
    def get_resource(cls, resource):
        objs = cls._lookup(resource)
        if not objs:
            raise ServiceResourceDoesNotExist
        data = {}
        for (path, obj) in objs:
            if path:
                z = data
                for i in path:
                    p = z
                    if i not in z:
                        z[i] = {}
                        z = z[i]
                p[i] = obj.get_state().get()
            else:
                return obj.get_state().get()
        return data

    @classmethod
    def _lookup(cls, resource):
        objs = []
        if not resource:
            return objs
        for k in cls.__registry:
            if k == resource or resource == '/' or (k.startswith(resource) and k[len(resource)] == '/'):
                path = [x for x in k[len(resource):].split('/') if x]
                objs.append((path, cls.__registry[k]))
        return objs


class ServiceStateChangeRegistry():
    __registry = {}

    @classmethod
    def notify(cls, resource, state):
        def _notify(resource, state):
            """Evaluate each resource and assess if it is parent or same level
            in the resource tree.  For each matching entry in the register, we
            need to notify the state change event
            """
            for (this_app, context) in cls.__registry:
                target = cls.__registry[(this_app, context)]
                if resource == target or target == '/' or (resource.startswith(target) and \
                                                           resource[len(target)] == '/'):
                    def expand(path, s):
                        """Expands a dict iteratively to depth of path"""
                        d = {}
                        z = d
                        p = None
                        for i in path:
                            p = z
                            z[i] = {}
                            z = z[i]
                        if p:
                            p[i] = s
                        else:
                            d = s
                        return d
                    path = [x for x in resource[len(target):].split('/') if x]
                    data = expand(path, state)
                    this_app.notify(resource, data)
        _notify(resource, state)

    @classmethod
    def register(cls, this_app, resource):
        cls.__registry[(this_app, resource)] = resource

    @classmethod
    def unregister(cls, this_app, resource):
        cls.__registry.pop((this_app, resource))

    @classmethod
    def unregister_all(cls, this_app):
        for (app, context) in list(cls.__registry):
            if app == this_app:
                del cls.__registry[(app, context)]


class ServiceStateMachine():
    def __init__(self, allowed_states=[], allowed_next_states={}, default_state=None):
        self._allowed_states = allowed_states
        self._allowed_next_states = allowed_next_states
        self._current_state = None
        self.validate(default_state.upper())
        self._current_state = default_state.upper()

    def validate(self, s):
        if self._current_state in self._allowed_next_states:
            if s.upper() not in self._allowed_next_states[self._current_state]:
                raise ServiceIllegalState
        elif s.upper() not in self._allowed_states:
            raise ServiceUnrecognisedState
        return True

    @property
    def state(self):
        return self._current_state

    @state.setter
    def state(self, s):
        self.validate(s.upper())
        self._current_state = s.upper()
