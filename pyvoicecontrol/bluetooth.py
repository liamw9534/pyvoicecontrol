from . import service
from . import bluetoothctl
import threading
import time


import logging


logger = logging.getLogger(__name__)


class Bluetooth(service.ServiceResource):
    def __init__(self, config):
        super().__init__(config['path'])
        self._config = config
        self._devices = {}

    def on_stop(self):
        self._stopping = True
        self._thread.join()
        if self._config['disconnect_on_exit']:
            self.disconnect_devices()
        service.ServiceResource.on_stop(self)

    def on_start(self):
        self._stopping = False
        self._state = service.ServiceStateMachine(['READY'], default_state='READY')
        self._bluetooth = bluetoothctl.Bluetoothctl()
        for x in self._config['devices']:
            self._devices[x] = { 'state':'UNKNOWN' }
        self._thread = threading.Thread(target=self.process_devices)
        self._thread.start()
        self._set_state_internal(force=True)

    def start_scan(self):
        logger.debug('Scan on')
        self._bluetooth.start_scan()

    def stop_scan(self):
        logger.debug('Scan off')
        self._bluetooth.stop_scan()

    def pair_device(self, device):
        logger.debug('Pairing %s...', device)
        self._bluetooth.pair(device, timeout=3.0)
        self._bluetooth.trust(device, timeout=1.0)

    def connect_device(self, device):
        logger.debug('Connecting %s...', device)
        self._bluetooth.connect(device, timeout=3.0)

    def disconnect_devices(self):
        logger.info('Disconnecting devices...')
        for x in self._devices:
            self._bluetooth.disconnect(x)

    def process_devices(self):
        while not self._stopping:
            devs = {}
            waiting_for_connection = False
            for d in self._config['devices']:
                devs[d] = {}
                state = self._bluetooth.get_device_info(d, timeout=1)
                logger.debug('device %s state %s', d, state)
                if not state:
                    logger.debug('device %s unavailable, scanning...', d)
                    waiting_for_connection = True
                    devs[d]['state'] = 'SCANNING'
                    self._proxy.start_scan()
                else:
                    if state['Paired'] == 'no':
                        waiting_for_connection = True
                        self._proxy.start_scan()
                        if d in self._devices and self._devices[d]['state'] != 'PAIRING':
                            logger.info('Pairing %s', d)
                        devs[d]['state'] = 'PAIRING'
                        self._proxy.pair_device(d)
                    elif state['Connected'] == 'no':
                        waiting_for_connection = True
                        self._proxy.start_scan()
                        if d in self._devices and self._devices[d]['state'] != 'CONNECTING':
                            logger.info('Connecting %s', d)
                        devs[d]['state'] = 'CONNECTING'
                        self._proxy.connect_device(d)
                    else:
                        if d in self._devices and self._devices[d]['state'] != 'CONNECTED':
                            logger.info('Connected %s', d)
                        devs[d]['state'] = 'CONNECTED'
                if not waiting_for_connection:
                    self._proxy.stop_scan()
            self._set_state_internal(devices=devs)
            time.sleep(2)

    def _set_state_internal(self, state=None, devices=None, force=False):
        """Use this to actuate state changes and notify other listeners
           of any state changes via ServiceStateChangeRegistry.notify()
        """
        try:
            changed = force
            if state and state != self._state.state:
                self._state.state = state
                changed = True
            if devices is not None and devices != self._devices:
                self._devices = devices
                changed = True
        finally:
            if changed:
                service.ServiceStateChangeRegistry.notify(self._path, self.get_state())

    def get_state(self):
        return { 'state': self._state.state, 'devices': self._devices  }
