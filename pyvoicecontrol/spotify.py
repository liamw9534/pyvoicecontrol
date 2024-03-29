from . import service
import logging
import spotipy
from nested_lookup import nested_lookup
from gi.repository import GObject
from spotipy.oauth2 import SpotifyOAuth


logger = logging.getLogger(__name__)


class SpotifyService(service.ServiceResource):
    def __init__(self, config):
        super().__init__(config['path'])
        self._config = config

    def on_start(self):
        self._state = service.ServiceStateMachine(['READY'], default_state='READY')
        self._now_playing = {}
        self._set_state_internal(force=True)
        service.ServiceStateChangeRegistry.register(self._proxy, '/speech/intent')
        service.ServiceStateChangeRegistry.register(self._proxy, '/input')
        scope = 'user-read-playback-state,user-modify-playback-state,user-read-currently-playing'
        self._auth = SpotifyOAuth(self._config['client_id'],
                                  self._config['client_secret'],
                                  self._config['redirect_uri'],
                                  scope=scope,
                                  open_browser=False
                                  )
        self._client = spotipy.Spotify(client_credentials_manager=self._auth)
        self._device = {}
        self.setup_device()
        self._timeout = GObject.timeout_add(int(self._config['scan_period'] * 1000), self._proxy.setup_device)

    def on_stop(self):
        GObject.source_remove(self._timeout)
        service.ServiceResource.on_stop(self)

    def notify(self, path, state):
        if path == '/speech/intent' and state['state'] == 'INTENT':
            self._proxy.handle_intent(state['intent'].get('intents', []), state['intent'].get('entities', {}))
        elif path == '/input' and state['state'] == 'ACTION':
            self._proxy.handle_input_action(state['action'])

    def handle_input_action(self, action):
            if 'skip_track' in action:
                self._skip_track()
            elif 'previous_track' in action:
                self._previous_track()
            elif 'stop' in action:
                self._stop_music()
            elif 'playpause' in action:
                self._toggle_music()
            elif 'pause' in action:
                self._pause_music()
            elif 'resume' in action:
                self._resume_music()
            else:
                logger.warn('ignoring "%s" action', action)                

    def handle_intent(self, intents, entities):
        for intent in intents:
            action = intent['name']
            logger.debug('intent=%s', intent)
            if 'skip_track' in action:
                self._skip_track()
            elif 'previous_track' in action:
                self._previous_track()
            elif 'stop' in action:
                self._stop_music()
            elif 'pause' in action:
                self._pause_music()
            elif 'resume' in action:
                self._resume_music()
            elif 'play_music' in action:
                self._play_music(entities)
            elif 'unshuffle' in action:
                self._unshuffle_music()
            elif 'shuffle' in action:
                self._shuffle_music()
            elif 'unloop' in action:
                self._unloop_music()
            elif 'loop' in action:
                self._loop_music()
            else:
                logger.warn('ignoring "%s" intent', action)

    def setup_device(self):
        devices = self._client.devices()
        if self._config['device']:
            logger.debug('devices: %s', devices)
            for x in devices['devices']:
                if x['name'] == self._config['device']:
                    if self._device.get('id', None) != x['id']:
                        logger.info('Using Spotify Connect device "%s" with id=%s', x['name'], x['id'])
                        self._device = x
                    return
            logger.warn('Did not find Spotify Connect device "%s"', self._config['device'])
        current = self._client.current_playback()
        if current:
            if self._device.get('id', None) != current['device']['id']:
                logger.warn('Using current Spotify Connect device id=%s instead', current['device']['id'])
                self._device = current['device']
            return
        else:
            device = devices['devices'][0] if devices.get('devices', None) else None
            if device:
                if self._device.get('id', None) != device['id']:
                    logger.warn('Using first available Spotify Connect device %s instead', device['name'])
                    self._device = device
                return
        self._device = {}
        logger.error('Did not find any Spotify Connect device on your network')
        return True

    def _skip_track(self):
        logger.info('_skip_track')
        self._client.next_track(device_id=self._device.get('id', None))

    def _previous_track(self):
        logger.info('_previous_track')
        self._client.previous_track(device_id=self._device.get('id', None))

    def _stop_music(self):
        logger.info('_stop_music')
        self._client.start_playback(device_id=self._device.get('id', None), uris=[])

    def _pause_music(self):
        logger.info('_pause_music')
        self._client.pause_playback(device_id=self._device.get('id', None))

    def _shuffle_music(self):
        logger.info('_shuffle_music')
        self._client.shuffle(state=True, device_id=self._device.get('id', None))

    def _unshuffle_music(self):
        logger.info('_unshuffle_music')
        self._client.shuffle(state=False, device_id=self._device.get('id', None))

    def _loop_music(self):
        logger.info('_loop_music')
        self._client.repeat(state='context', device_id=self._device.get('id', None))

    def _unloop_music(self):
        logger.info('_unloop_music')
        self._client.repeat(state='off', device_id=self._device.get('id', None))

    def _toggle_music(self):
        current = self._client.current_playback()
        if current and current['is_playing']:
            self._pause_music()
        else:
            self._resume_music()

    def _resume_music(self):
        logger.info('_resume_music')
        self._client.start_playback(device_id=self._device.get('id', None))

    def _play_music(self, entities):
        logger.debug('_play_music entities=%s', entities)
        item = entities.get('playable_item:playable_item', [{}])[0].get('value', None)
        author = entities.get('playable_author:playable_author', [{}])[0].get('value', None)
        if item and author is None:
            for tag in ['track', 'album', 'artists', 'artist']:
                if item.startswith(tag + ' '):
                    subst_tag = 'artist' if tag == 'artists' else tag
                    item = item.replace(tag + ' ', subst_tag + ':')
            logger.info('search term: "%s"', item)
            t = 'artist,album,track'
            result = self._client.search(item, type=t, limit=self._config['limit'])
            uris = [x for x in nested_lookup('uri', result) if ':track:' in x]
            logger.info('got %s results', len(uris))
            if uris:
                self._client.start_playback(device_id=self._device.get('id', None), uris=uris)
        elif item:
            for tag in ['track', 'album']:
                if item.startswith(tag + ' '):
                    item = item.replace(tag + ' ', tag + ':')
            search_term = item + ' artist:' + author
            logger.info('search term: "%s"', search_term)
            t = 'album,track'
            result = self._client.search(search_term, type=t, limit=self._config['limit'])
            uris = [x for x in nested_lookup('uri', result) if ':track:' in x]
            logger.info('got %s results', len(uris))
            if uris:
                self._client.start_playback(device_id=self._device.get('id', None), uris=uris)

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
        return { 'state': self._state.state, 'now_playing': self._now_playing }
