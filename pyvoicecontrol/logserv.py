import logging
from . import service
from .raw import RawSocketHandler


class LogService(service.ServiceResource):
    """Debug logging control resource"""
    def __init__(self, config):
        super().__init__(config['path'])
        self._handler = RawSocketHandler(port=config['port'])
        self._debug_level = service.ServiceStateMachine(['WARN', 'INFO', 'ERROR', 'DEBUG'], default_state=config['level'])
        self._state = service.ServiceStateMachine(['ON', 'OFF'], default_state='ON' if config['enable'] else 'OFF')
        logging.basicConfig(format='%(asctime)s\t%(module)s\t%(levelname)s\t%(message)s')
        self._set_state_internal(self._state.state, self._debug_level.state)

    def on_stop(self):
        #logger = logging.getLogger()
        #if self._state.state == 'ON':
        #    logger.removeHandler(self._handler)
        service.ServiceResource.on_stop(self)

    def _set_state_internal(self, state=None, debug_level=None):
        
        logger = logging.getLogger()
        #if state and state == 'ON':
        #    logger.addHandler(self._handler)
        #elif state and state == 'OFF':
        #    logger.removeHandler(self._handler)

        if debug_level and debug_level == 'DEBUG':
            logger.setLevel(logging.DEBUG)
        elif debug_level and debug_level == 'WARN':
            logger.setLevel(logging.WARN)
        elif debug_level and debug_level == 'ERROR':
            logger.setLevel(logging.ERROR)
        elif debug_level and debug_level == 'INFO':
            logger.setLevel(logging.INFO)

        changed = (state and state != self._state.state) or (debug_level and debug_level != self._debug_level.state)
        self._state.state = state if state else self._state.state
        self._debug_level.state = debug_level if debug_level else self._debug_level.state

        if changed:
            service.ServiceStateChangeRegistry.notify(self._path, self.get_state())

    def set_state(self, state):
        self._set_state_internal(state=state.get('state', None),
                                 debug_level=state.get('debug_level', None))

    def get_state(self):
        return { 'state': self._state.state,
                 'debug_level': self._debug_level.state }
