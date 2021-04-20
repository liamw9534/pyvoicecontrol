from gi import require_version
require_version('Gst', '1.0')
from gi.repository import Gst, GObject

import logging
import os

from . import service


logger = logging.getLogger(__name__)


models_dir = os.path.dirname(os.path.realpath(__file__)) + '/resources/models/'


class SnowboyHotwordDetector(service.ServiceResource):
    def __init__(self, config):
        super().__init__(config['path'])
        self._state = service.ServiceStateMachine(['LISTENING', 'DETECT_START', 'DETECT_ABORT', 'DETECT_STOP'], default_state='LISTENING')
        self._config = config

    def on_start(self):
        self._timeout = None
        self._pipeline = Gst.parse_launch(self._config['pipeline'].format(models_dir + self._config['resource'],
                                                                   models_dir + self._config['model'],
                                                                   self._config['sensitivity'],
                                                                   self._config['vad_hysteresis'],
                                                                   self._config['vad_threshold_db'],
                                                                   0,
                                                                   self._config['port']))
        self._pipeline.set_state(Gst.State.PLAYING)
        self._sb = self._pipeline.get_by_name('sb')
        self._sb.connect('hotword-detect', self._on_hotword_detect)
        self._rm = self._pipeline.get_by_name('rm')
        self._activity_detected = False
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._on_bus_message)
        self._set_state_internal(force=True)

    def _on_bus_message(self, _, message):
        if message.type == Gst.MessageType.ELEMENT and message.src == self._rm:
            s = message.get_structure().to_string()
            if 'silence_detected' in s:
                self._vad_silence_detected()
                logger.info('vad inactive')
            elif 'silence_finished' in s:
                self._vad_silence_finished()
                logger.info('vad active')

    def _vad_timeout(self):
        if not self._activity_detected:
            logger.info('vad timeout')
            self._stop_recording('timeout')
        self._timeout = None
        return False

    def _vad_silence_detected(self):
        self._stop_recording('silence')

    def _vad_silence_finished(self):
        self._activity_detected = True
        self._rm.set_property('minimum-silence-time', int(self._config['vad_min_silence_period_sec'] * 1000000000))

    def _on_hotword_detect(self, obj, index):
        logger.info('hotword detected')
        self._set_state_internal(state='DETECT_START')
        self._activity_detected = False
        self._sb.set_property('listen', False)
        self._rm.set_property('gate', False)
        self._rm.set_property('silent', False)
        self._timeout = GObject.timeout_add(int(self._config['vad_max_silence_period_sec']*1000), self._vad_timeout)

    def _stop_recording(self, cause):
        if self._state.state == 'DETECT_START':
            if self._activity_detected:
                self._set_state_internal(state='DETECT_STOP')
            elif cause == 'timeout':
                self._set_state_internal(state='DETECT_ABORT') 
            else:
                return
            if self._timeout:
                GObject.source_remove(self._timeout)
                self._timeout = None
            self._sb.set_property('listen', True)
            self._rm.set_property('gate', True)
            self._rm.set_property('silent', True)
            self._rm.set_property('minimum-silence-time', 0)
            self._set_state_internal(state='LISTENING')

    def _set_state_internal(self, state=None, force=False):
        try:
            changed = force
            if state and state != self._state.state:
                self._state.state = state
                changed = True
        finally:
            if changed:
                service.ServiceStateChangeRegistry.notify(self._path, self.get_state())

    def get_state(self):
        return { 'state': self._state.state }
