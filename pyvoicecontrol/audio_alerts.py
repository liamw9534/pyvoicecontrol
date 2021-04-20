from gi import require_version
require_version('Gst', '1.0')
from gi.repository import Gst

from . import service
import logging
import os


logger = logging.getLogger(__name__)


sounds_dir = os.path.dirname(os.path.realpath(__file__)) + '/resources/sounds/'


def wrapped_call(fn, **kwargs):
    return lambda *args: fn(*args, **kwargs)


class AudioAlerts(service.ServiceResource):
    def __init__(self, config):
        super().__init__(config['path'])
        self._state = service.ServiceStateMachine(['READY', 'PLAYING'], default_state='READY')
        self._config = config
        self._setup_triggers(config['triggers'])
        self._set_state_internal(forced=True)

    def notify(self, path, state):
        attrs = self._triggers.get(path, {})
        for a in attrs:
            value = state.get(a, None)
            if value is dict:
                for k in value:
                    d = { k: value[k] }
                    f = attrs[a].get(str(d), None)
                    if f:
                        self._proxy.launch_pipeline(f)
            else:
                f = attrs[a].get(str(value), None)
                if f:
                    self._proxy.launch_pipeline(f)

    def _setup_triggers(self, triggers):
        self._triggers = {}
        for item in triggers:
            resource, attr, value, f = item.strip().split(':')
            if '.' in attr:
                a, b = attr.split('.')
                attr = a
                value = { b: value }
            if resource not in self._triggers:
                self._triggers[resource] = {}
                service.ServiceStateChangeRegistry.register(self._proxy, resource)
            if attr not in self._triggers[resource]:
                self._triggers[resource][attr] = {}
            self._triggers[resource][attr][str(value)] = f

    def _bus_handler(self, bus, msg, pipeline=None):
        """We use the bus handler to intercept pipeline messages and
           update the resource state when audio playing starts and ends.
        """
        mtype = msg.type
        if mtype == Gst.MessageType.EOS:
            logger.debug('EOS')
            self._set_state_internal(state='READY')
            pipeline.set_state(Gst.State.NULL)
        elif mtype == Gst.MessageType.STATE_CHANGED:
            old, new, pending = msg.parse_state_changed()
            state = Gst.Element.state_get_name(new)
            logger.debug('STATE_CHANGED: %s', state)
            if state == 'READY':
                self._set_state_internal(state='PLAYING')
        elif mtype == Gst.MessageType.ERROR:
            logger.debug('ERROR')
            self._set_state_internal(state='READY')
            pipeline.set_state(Gst.State.NULL)

    def launch_pipeline(self, audio_sample):
        logger.debug('Launching audio pipeline with %s...', audio_sample)
        pipeline_str = self._config['pipeline'].format(sounds_dir + '/' + audio_sample, self._config['volume'])
        pipeline = Gst.parse_launch(pipeline_str)
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', wrapped_call(self._bus_handler, pipeline=pipeline))
        pipeline.set_state(Gst.State.PLAYING)

    def _set_state_internal(self, state=None, forced=True):
        try:
            changed = forced
            if state and state != self._state.state:
                self._state.state = state
                changed = True
        finally:
            if changed:
                service.ServiceStateChangeRegistry.notify(self._path, self.get_state())

    def get_state(self):
        return { 'state': self._state.state }
