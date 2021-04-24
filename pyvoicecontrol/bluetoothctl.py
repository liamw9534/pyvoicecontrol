import pexpect
import subprocess
import sys
import logging


logger = logging.getLogger(__name__)


class BluetoothctlError(Exception):
    """This exception is raised, when bluetoothctl fails to start."""
    pass


class Bluetoothctl:
    """A wrapper for bluetoothctl utility."""

    def __init__(self):
        #subprocess.check_output("rfkill unblock bluetooth", shell = True)
        self.child = pexpect.spawn("bluetoothctl", echo = False)
        #self.child.logfile = sys.stdout.buffer

    def _flush(self):
        self.child.expect(r'.+', timeout=0.1)
        
    def execute_command(self, command, requires=[], timeout=None):
        self.child.send(command + "\n")
        try:
            exp = [pexpect.EOF] + requires if requires else [pexpect.EOF, "#"]
            result = self.child.expect(exp, timeout=timeout)
            if result == 0:
                raise BluetoothctlError("Bluetoothctl failed after running " + command)
            return result - 1 if requires else self.child.before.decode('ascii').split("\r\n")
        except:
            return ''

    def start_scan(self):
        try:
            self.execute_command("scan on", timeout=1)
        except BluetoothctlError as e:
            print(e)
            return None

    def stop_scan(self):
        try:
            self.execute_command("scan off", timeout=1)
        except BluetoothctlError as e:
            print(e)
            return None

    def make_discoverable(self):
        try:
            self.execute_command("discoverable on", timeout=1)
        except BluetoothctlError as e:
            print(e)
            return None

    def parse_device_info(self, info_string):
        device = {}
        block_list = ["[\x1b[0;", "removed"]
        string_valid = not any(keyword in info_string for keyword in block_list)

        if string_valid:
            try:
                device_position = info_string.index("Device")
            except ValueError:
                pass
            else:
                if device_position > -1:
                    attribute_list = info_string[device_position:].split(" ", 2)
                    device = {
                        "mac_address": attribute_list[1],
                        "name": attribute_list[2]
                    }
        return device

    def get_available_devices(self):
        try:
            out = self.execute_command("devices", timeout=1)
        except BluetoothctlError as e:
            print(e)
            return None
        else:
            available_devices = []
            for line in out:
                device = self.parse_device_info(line)
                if device:
                    available_devices.append(device)
            return available_devices

    def get_paired_devices(self):
        try:
            out = self.execute_command("paired-devices", timeout=1)
        except BluetoothctlError as e:
            print(e)
            return None
        else:
            paired_devices = []
            for line in out:
                device = self.parse_device_info(line)
                if device:
                    paired_devices.append(device)

            return paired_devices

    def get_discoverable_devices(self):
        available = self.get_available_devices()
        paired = self.get_paired_devices()
        return [d for d in available if d not in paired]

    def get_device_info(self, mac_address, timeout=1):
        try:
            for _ in range(3):
                out = self.execute_command("info " + mac_address, timeout=timeout)
                if 'Device' in out:
                    break
        except BluetoothctlError as e:
            print(e)
            return None
        else:
            items = [x.strip().replace('\t', '') for x in out]
            res = {}
            for x in items:
                k = x.split(':')
                if len(k) == 2:
                    if ' ' in k[0]:
                        continue
                    if k[0] in res and type(res[k[0]]) is not list:
                        res[k[0]] = [res[k[0]]]
                        res[k[0]].append(k[1].strip())
                    else:
                        res[k[0]] = k[1].strip()
            return res

    def trust(self, mac_address, timeout=3):
        try:
            res = self.execute_command("trust " + mac_address, requires=["trust succeeded", "not available"], timeout=timeout)
        except BluetoothctlError as e:
            print(e)
        else:
            return res == 0

    def pair(self, mac_address, timeout=5):
        try:
            res = self.execute_command("pair " + mac_address, requires=["Pairing successful", "Failed to pair", "not available"], timeout=timeout)
        except BluetoothctlError as e:
            print(e)
        else:
            return res == 0

    def remove(self, mac_address, timeout=3):
        try:
            res = self.execute_command("remove " + mac_address, requires=["Device has been removed", "not available"], timeout=timeout)
        except BluetoothctlError as e:
            print(e)
        else:
            return res == 0

    def connect(self, mac_address, timeout=5):
        try:
            res = self.execute_command("connect " + mac_address, requires=["Connection successful", "Failed to connect"], timeout=timeout)
        except BluetoothctlError as e:
            print(e)
        else:
            return res == 0

    def disconnect(self, mac_address, timeout=3):
        try:
            res = self.execute_command("disconnect " + mac_address, requires=["Successful disconnected", "Failed to disconnect"], timeout=timeout)
        except BluetoothctlError as e:
            print(e)
        else:
            return res == 0
