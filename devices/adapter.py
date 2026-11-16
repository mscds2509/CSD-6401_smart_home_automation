"""(5) ADAPTER - make an old vendor device with a different API look like a SmartDevice."""
from .base import SmartDevice


class LegacyVendorDevice:                 # Adaptee (cannot be modified)
    def __init__(self):
        self._power = 0

    def power_on(self):
        self._power = 1

    def power_off(self):
        self._power = 0

    def read_state(self):
        return f"POWER={self._power}"


class LegacyDeviceAdapter(SmartDevice):   # Adapter
    def __init__(self, name: str, legacy_device: LegacyVendorDevice):
        self.name = name
        self._legacy_device = legacy_device

    def turn_on(self):
        self._legacy_device.power_on()

    def turn_off(self):
        self._legacy_device.power_off()

    def get_status(self):
        on = self._legacy_device.read_state() == "POWER=1"
        return f"{self.name}: {'ON' if on else 'OFF'}"
