"""(6) BRIDGE - device abstraction (light/fan) separated from the protocol driver (MQTT/Wi-Fi)."""
from abc import abstractmethod, ABC
from .base import SmartDevice


class DeviceDriver(ABC):                  # Implementor
    @abstractmethod
    def send_command(self, command: str): ...

    @abstractmethod
    def get_state(self) -> str: ...


class _BaseDriver(DeviceDriver):
    protocol = "?"

    def __init__(self):
        self._state = "OFF"

    def send_command(self, command):
        print(f"      [{self.protocol}] -> {command}")
        if command in ("ON", "OFF"):
            self._state = command

    def get_state(self):
        return self._state


class MqttDriver(_BaseDriver):            # ConcreteImplementor
    protocol = "MQTT"


class WifiDriver(_BaseDriver):            # ConcreteImplementor
    protocol = "WIFI"


class SmartDeviceBridge(SmartDevice):     # Abstraction (holds the driver)
    def __init__(self, name: str, driver: DeviceDriver):
        self.name = name
        self._driver = driver             # # driver: DeviceDriver

    def turn_on(self):
        self._driver.send_command("ON")

    def turn_off(self):
        self._driver.send_command("OFF")

    def get_status(self):
        return f"{self.name}: {self._driver.get_state()}"


class LightDevice(SmartDeviceBridge):     # RefinedAbstraction
    def __init__(self, name, driver):
        super().__init__(name, driver)
        self.brightness = 100

    def set_brightness(self, level: int):
        self.brightness = level
        self._driver.send_command(f"BRIGHTNESS={level}")


class FanDevice(SmartDeviceBridge):       # RefinedAbstraction
    def __init__(self, name, driver):
        super().__init__(name, driver)
        self.speed = 1

    def set_speed(self, level: int):
        self.speed = level
        self._driver.send_command(f"SPEED={level}")
