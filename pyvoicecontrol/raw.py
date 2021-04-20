import logging
import socket


class RawSocketHandler(logging.Handler):
    """Logging handler to send logging over UDP"""
    def __init__(self, host='127.0.0.1', port=51010):
        logging.Handler.__init__(self)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._address = (host, port)

    def emit(self, record):
        msg = self.format(record) + '\n'
        self._socket.sendto(msg.encode('UTF-8'), self._address)

    def close(self):
        self._socket.close()
        logging.Handler.close(self)
