from . import service
import logging
import asyncio
import threading
import pulsectl_asyncio


logger = logging.getLogger(__name__)


class PulseClient():
    def __init__(self, echo_cancel=False, src_volume=None, sink_volume=None):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._async_loop)
        self._thread.daemon = True
        self._thread.start()
        self._pulse = pulsectl_asyncio.PulseAsync(loop=self._loop)
        asyncio.run_coroutine_threadsafe(self.pulse_task(), self._loop)
        self._src_volume = src_volume/100.0 if src_volume is not None else None
        self._sink_volume = sink_volume/100.0 if sink_volume is not None else None
        self._echo_cancel = echo_cancel
        self._mute = False

    def _async_loop(self):
        self._loop.run_forever()
        self._loop.close()

    def increment_volume(self, step):
        new_level = min(1.0, self._sink_volume + (step / 100.0))
        asyncio.run_coroutine_threadsafe(self.sink_volume(new_level), self._loop)

    def decrement_volume(self, step):
        new_level = max(0, self._sink_volume - (step / 100.0))
        asyncio.run_coroutine_threadsafe(self.sink_volume(new_level), self._loop)

    def set_volume(self, level):
        asyncio.run_coroutine_threadsafe(self.sink_volume(level/100.0), self._loop)

    def set_mute(self, state):
        asyncio.run_coroutine_threadsafe(self.sink_mute(state), self._loop)

    @property
    def mute(self):
        return self._mute

    async def sink_volume(self, level):
        server_info = await self._pulse.server_info()
        default_sink = await self._pulse.get_sink_by_name(server_info.default_sink_name)
        self._sink_volume = level
        await self._pulse.volume_set_all_chans(default_sink, self._sink_volume)

    async def sink_mute(self, state):
        server_info = await self._pulse.server_info()
        default_sink = await self._pulse.get_sink_by_name(server_info.default_sink_name)
        await self._pulse.mute(default_sink, state)
        self._mute = state

    async def cleanup(self):
        if self._echo_cancel:
            await self.unload_echo_cancel()

    async def load_echo_cancel(self):
        await self._pulse.module_load('module-echo-cancel', args='aec_args="analog_gain_control=0 digital_gain_control=0"')

    async def load_switch_on_connect(self):
        await self._pulse.module_load('module-switch-on-connect')

    async def unload_echo_cancel(self, unload=True):
        unloaded = False
        modules = await self._pulse.module_list()
        for x in modules:
            if x.name == 'module-echo-cancel':
                if unload:
                    await self._pulse.module_unload(x.index)
                unloaded = True
        return unloaded

    async def configure_volume(self):
        server_info = await self._pulse.server_info()
        default_src = await self._pulse.get_source_by_name(server_info.default_source_name)
        default_sink = await self._pulse.get_sink_by_name(server_info.default_sink_name)
        self._mute = default_sink.mute
        if self._src_volume is not None:
            await self._pulse.volume_set_all_chans(default_src, self._src_volume)
        if self._sink_volume is not None:
            await self._pulse.volume_set_all_chans(default_sink, self._sink_volume)
        else:
            self._sink_volume = default_sink.volume.value_flat
        logger.info('default source: %s', default_src)
        logger.info('default sink: %s', default_sink)

    async def pulse_task(self):
        await self._pulse.connect(wait=True)
        await self.load_switch_on_connect()
        if self._echo_cancel and not await self.unload_echo_cancel(unload=False):
            await self.load_echo_cancel()
        await self.configure_volume()
        async for event in self._pulse.subscribe_events('sink', 'source'):
            if event.t == 'new':
                logger.debug('Pulse event: %s', event)
                if event.facility == 'sink':
                    sinks = await self._pulse.sink_list()
                    for x in sinks:
                        if x.index == event.index:
                            if 'echo cancel' not in x.description:
                                logger.info('New sink %s', x)
                                if self._echo_cancel:
                                    await self.unload_echo_cancel()
                                    await self.load_echo_cancel()
                                await self.configure_volume()
                elif event.facility == 'source':
                    sources = await self._pulse.source_list()
                    for x in sources:
                        if x.index == event.index:
                            if 'echo cancel' not in x.description:
                                logger.info('New source %s', x)
                                if self._echo_cancel:
                                    await self.unload_echo_cancel()
                                    await self.load_echo_cancel()
                                await self.configure_volume()

    def stop(self):
        future = asyncio.run_coroutine_threadsafe(self.cleanup(), self._loop)
        future.result()
        self._pulse.close()

    
class Pulse(service.ServiceResource):
    def __init__(self, config):
        super().__init__(config['path'])
        self._config = config

    def on_start(self):
        self._state = service.ServiceStateMachine(['READY'], default_state='READY')
        self._pulse = PulseClient(self._config['echo_cancel'], self._config['src_vol'], self._config['sink_vol'])
        service.ServiceStateChangeRegistry.register(self._proxy, '/speech/detector')
        service.ServiceStateChangeRegistry.register(self._proxy, '/speech/intent')
        service.ServiceStateChangeRegistry.register(self._proxy, '/input')
        self._set_state_internal(force=True)

    def on_stop(self):
        self._pulse.stop()
        service.ServiceResource.on_stop(self)

    def notify(self, path, state):
        if path == '/speech/detector' and self._config['volume_ducking'] and self._config['local_volume_control']:
            if state['state'] == 'DETECT_START':
                self._mute_state = self._pulse.mute
                self._pulse.set_mute(True)
            elif state['state'] == 'DETECT_STOP':
                self._pulse.set_mute(self._mute_state)
            elif state['state'] == 'DETECT_ABORT':
                self._pulse.set_mute(self._mute_state)
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
            logger.info('set volume louder (+%s)', self._config['volume_step_size'])
            self._pulse.increment_volume(self._config['volume_step_size'])

    def _volume_lower(self):
        if self._config['local_volume_control']:
            logger.info('set volume quieter (-%s)', self._config['volume_step_size'])
            self._pulse.decrement_volume(self._config['volume_step_size'])

    def _volume(self, entities):
        locations = entities.get('room:room', [])
        levels = entities.get('wit$number:level', [])
        for x in levels:
            level = x['value']
            if locations:
                for y in locations:
                    location = y['value']
                    if location == self._config['own_location'] and self._config['local_volume_control']:
                        logger.info('set volume %s in %s', level, location)
                        self._pulse.set_volume(level)
            else:
                if self._config['local_volume_control']:
                    logger.info('set volume %s in %s', level, self._config['own_location'])
                    self._pulse.set_volume(level)

    def _mute(self, state):
        if self._config['local_volume_control']:
            self._pulse.set_mute(state)

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
