from . import service
import logging
import snapcast.control
import asyncio


logger = logging.getLogger(__name__)


class Snapcast(service.ServiceResource):
    def __init__(self, config):
        super().__init__(config['path'])
        self._config = config
        self._state = service.ServiceStateMachine(['READY'], default_state='READY')
        self._set_state_internal(force=True)
        service.ServiceStateChangeRegistry.register(self._proxy, '/speech/detector')
        service.ServiceStateChangeRegistry.register(self._proxy, '/speech/intent')
        service.ServiceStateChangeRegistry.register(self._proxy, '/input')
        self._loop = asyncio.get_event_loop()
        self._server = self._loop.run_until_complete(snapcast.control.create_server(self._loop, config['server']))
        self._client = self._server.client(config['own_location'])
        self._mute_state = self._client.muted

    def notify(self, path, state):
        if path == '/speech/detector' and self._config['volume_ducking'] and self._config['local_volume_control']:
            if state['state'] == 'DETECT_START':
                self._mute_state = self._client.muted
                self._mute(True)
            elif state['state'] == 'DETECT_STOP':
                self._mute(self._mute_state)
            elif state['state'] == 'DETECT_ABORT':
                self._mute(self._mute_state)
        elif path == '/speech/intent' and state['state'] == 'INTENT':
            self._proxy.process_intent(state['intent'].get('intents', []), state['intent'].get('entities', {}))
        elif path == '/input' and state['state'] == 'ACTION':
            self._proxy.handle_input_action(state['action'])

    def handle_input_action(self, action):
        if 'volume_louder' in action:
            self._volume_higher()
        elif 'volume_quieter' in action:
            self._volume_lower()
        else:
            logger.warn('ignoring "%s" action', action)                

    def process_intent(self, intents, entities):
        for intent in intents:
            action = intent['name']
            if 'unmute' in action:
                self._mute(False)
            elif 'mute' in action:
                self._mute(True)
            elif 'volume_louder' in action:
                self._volume_higher()
            elif 'volume_lower' in action:
                self._volume_lower()
            elif 'volume' in action:
                self._volume(entities)
            else:
                logger.warn('ignoring "%s" intent', action)

    def _volume_higher(self):
        if self._config['local_volume_control']:
            level = min(100, self._client.volume + self._config['volume_step_size'])
            logger.info('set volume louder (+%s->%s) in %s', self._config['volume_step_size'], level, self._config['own_location'])
            self._loop.run_until_complete(self._client.set_volume(level))

    def _volume_lower(self):
        if self._config['local_volume_control']:
            level = max(0, self._client.volume - self._config['volume_step_size'])
            logger.info('set volume quieter (-%s->%s) in %s', self._config['volume_step_size'], level, self._config['own_location'])
            self._loop.run_until_complete(self._client.set_volume(level))
        
    def _volume(self, entities):
        locations = entities.get('room:room', [])
        levels = entities.get('wit$number:level', [])
        for x in levels:
            level = x['value']
            if locations:
                for y in locations:
                    location = y['value']
                    client = self._server.client(location)
                    logger.info('set volume %s in %s', level, location)
                    self._loop.run_until_complete(client.set_volume(level))
            else:
                if self._config['local_volume_control']:
                    logger.info('set volume %s in %s', level, self._config['own_location'])
                    self._loop.run_until_complete(self._client.set_volume(level))

    def _mute(self, state):
        if self._config['local_volume_control']:
            self._loop.run_until_complete(self._client.set_muted(state))

    def _set_state_internal(self, state=None, force=False):
        """Use this to actuate state changes and notify other listeners
           of any state changes via ServiceStateChangeRegistry.notify()
        """
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
