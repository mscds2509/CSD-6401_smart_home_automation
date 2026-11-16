"""(7) DECORATOR - add energy monitoring to ANY SmartDevice without changing it."""
import time
from .base import SmartDevice


class DeviceDecorator(SmartDevice):       # abstract Decorator (is-a and has-a SmartDevice)
    def __init__(self, device: SmartDevice):
        self._device = device             # # device

    def turn_on(self):
        self._device.turn_on()

    def turn_off(self):
        self._device.turn_off()

    def get_status(self):
        return self._device.get_status()


class EnergyMonitoringDecorator(DeviceDecorator):
    def __init__(self, device, watts=10.0, clock=time.monotonic):
        super().__init__(device)
        self._watts, self._clock = watts, clock
        self._on_since = None
        self._energy_kwh = 0.0

    def turn_on(self):
        super().turn_on()
        if self._on_since is None:
            self._on_since = self._clock()

    def turn_off(self):
        super().turn_off()
        if self._on_since is not None:
            hours = (self._clock() - self._on_since) / 3600
            self._energy_kwh += self._watts * hours / 1000
            self._on_since = None

    def get_energy_usage(self) -> float:
        return self._energy_kwh
