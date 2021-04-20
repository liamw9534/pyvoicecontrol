from . import service
import logging


logger = logging.getLogger(__name__)


class Template(service.ServiceResource):
    """
    Template resource
    """
    def __init__(self, config):
        super().__init__(config['path'])
        self._config = config

    def on_start(self):
        """Setup your service here and set any default state params that your service
           provides.  Optionally register to state changes on other services using
           ServiceStateChangeRegistry.register()
        """
        self._state = service.ServiceStateMachine(['READY'], default_state='READY')
        self._temperature = 50
        self._set_state_internal(force=True)

    def notify(self, path, state):
        """
        If your service relies on other services, you can monitor their
        state changes here.
        """
        pass

    def _set_state_internal(self, state=None, temperature=None, force=False):
        """Use this to actuate state changes and notify other listeners
           of any state changes via ServiceStateChangeRegistry.notify()
        """
        try:
            changed = force
            if state and state != self._state.state:
                self._state.state = state
                changed = True
            if temperature is not None and temperature != self._temperature:
                changed = True
                self._temperature = temperature
        finally:
            if changed:
                service.ServiceStateChangeRegistry.notify(self._path, self.get_state())

    def set_state(self, state):
        if state.get('temperature', None):
            self._set_state_internal(temperature=state['temperature'])

    def get_state(self):
        return { 'state': self._state.state,
                 'temperature': self._temperature }
