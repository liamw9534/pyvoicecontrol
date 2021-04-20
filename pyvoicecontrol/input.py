from . import service
import logging
import evdev

from gi.repository import GObject


logger = logging.getLogger(__name__)


class Input(service.ServiceResource):
    def __init__(self, config):
        super().__init__(config['path'])
        self._config = config
        self._files = {}
        self._devices = []
        self._action_map = {}
        self._parse_action_map()

    def _parse_action_map(self):
        for x in self._config['action_map']:
            key,action = x.split(':')
            self._action_map[key] = action

    def on_start(self):
        """Setup your service here and set any default state params that your service
           provides.  Optionally register to state changes on other services using
           ServiceStateChangeRegistry.register()
        """
        self._state = service.ServiceStateMachine(['IDLE', 'ACTION'], default_state='IDLE')
        self._action = None
        self._set_state_internal(force=True)
        self._timeout = GObject.timeout_add(1000, self._proxy.update_available_inputs)

    def update_available_inputs(self):
        devices = [evdev.InputDevice(x) for x in evdev.list_devices()]
        for x in devices:
            if x.phys not in self._devices and \
                (not self._config['devices'] or \
                 (x.name in self._config['devices'] or \
                  x.path in self._config['devices'] or \
                  x.phys in self._config['devices'])):
                logger.info('New device %s added', x.name)
                self._devices.append(x.phys)
                self._files[x.fileno()] = x
                GObject.io_add_watch(x.fileno(), GObject.IO_IN, self.io_handler)
        return True

    def io_handler(self, fd, _):
        device = self._files[fd]
        event = device.read_one()
        self._proxy.handle_key_event(event)
        return True

    def handle_key_event(self, event):
        if event.type == evdev.KeyEvent.key_down and event.value == evdev.KeyEvent.key_down:
            keys = evdev.ecodes.keys[event.code]
            logger.info('key press: %s', keys)
            if type(keys) is not list:
                keys = [keys]
            for key in keys:
                if key in self._action_map:
                    self._set_state_internal(state='ACTION', action=self._action_map[key])
        else:
            self._set_state_internal(state='IDLE')

    def _set_state_internal(self, state=None, action=None, force=False):
        """Use this to actuate state changes and notify other listeners
           of any state changes via ServiceStateChangeRegistry.notify()
        """
        try:
            changed = force
            if state and state != self._state.state:
                self._state.state = state
                changed = True
            if action is not None and action != self._action:
                self._action = action
                changed = True
        finally:
            if changed:
                service.ServiceStateChangeRegistry.notify(self._path, self.get_state())

    def get_state(self):
        return { 'state': self._state.state,
                 'action': self._action }
