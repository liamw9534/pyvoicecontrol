import logging
import requests
import socket
import sys
import json

from gi.repository import GObject

from . import service


logger = logging.getLogger(__name__)


class WitAISpeechService(service.ServiceResource):
    def __init__(self, config):
        super().__init__(config['path'])
        self._state = service.ServiceStateMachine(['IDLE', 'POSTING', 'INTENT'], default_state='IDLE')
        self._intent = {}
        self._config = config

    def on_start(self):
        self._buffered_audio = bytes()
        self._fd = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self._fd.bind(('', self._config['port']))
        GObject.io_add_watch(self._fd.fileno(), GObject.IO_IN, self.io_handler)
        self._set_state_internal(force=True)
        service.ServiceStateChangeRegistry.register(self._proxy, '/speech/detector')

    def io_handler(self, fd, flags):
        msg, _ = self._fd.recvfrom(1024*1024)
        self._buffered_audio += msg
        logger.debug('rx data length %s bytes', len(msg))
        return True

    def notify(self, _, state):
        if state['state'] == 'DETECT_STOP':
            self.handle_request()
        elif state['state'] == 'LISTENING':
            self._buffered_audio = bytes()

    def handle_request(self):

        if len(self._buffered_audio) == 0:
            logger.warn('No audio buffered')
            return

        self._buffered_audio = self._buffered_audio[:-(self._config['tail_discard_samples']*2)]

        token = self._config['token']
        headers = {'Authorization': 'Bearer ' + token,
                   'Content-Type': '{}; encoding={}; bits={}; rate={}; endian={}'.format(
                       self._config['content'], self._config['encoding'], self._config['bits'],
                       self._config['rate'], self._config['endian']
                       )
                   }
        url = self._config['url']

        try:
            logger.info('Posting to wit server')
            self._set_state_internal(state='POSTING')
            r = requests.post(url, headers=headers, data=self._buffered_audio)
            logger.debug('Got wit result %s', r.text)
            self._decode_result(r.text)
            self._set_state_internal(state='IDLE')
        except:
            logger.error('Failed to post request:', sys.exc_info())
            self._set_state_internal(state='IDLE')
        finally:
            if self._config['output_file']:
                with open(self._config['output_file'], 'wb') as f:
                    f.write(self._buffered_audio)

    def _decode_result(self, result):
        intent = json.loads(result)
        logger.info('you said "%s"', intent.get('text', ''))
        self._set_state_internal(state='INTENT', intent=intent)

    def _set_state_internal(self, state=None, intent=None, force=False):
        try:
            changed = force
            if state and state != self._state.state:
                self._state.state = state
                changed = True
            if intent:
                self._intent = intent
                changed = True
        finally:
            if changed:
                service.ServiceStateChangeRegistry.notify(self._path, self.get_state())

    def get_state(self):
        return { 'state': self._state.state, 'intent': self._intent }
