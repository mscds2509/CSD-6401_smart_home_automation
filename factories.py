"""(1) ABSTRACT FACTORY  - families of devices per protocol (MQTT family / Wi-Fi family)
   (4) FACTORY METHOD   - one creator per device TYPE (light / fan)"""
from abc import ABC, abstractmethod
from config import HomeConfig
from devices.bridge import LightDevice, FanDevice, MqttDriver, WifiDriver


# ---------------- Abstract Factory ----------------
class DeviceFamilyFactory(ABC):
    @abstractmethod
    def create_light(self, name) -> LightDevice: ...

    @abstractmethod
    def create_fan(self, name) -> FanDevice: ...


class MqttFactory(DeviceFamilyFactory):
    def create_light(self, name):
        return LightDevice(name, MqttDriver())

    def create_fan(self, name):
        return FanDevice(name, MqttDriver())


class WifiFactory(DeviceFamilyFactory):
    def create_light(self, name):
        return LightDevice(name, WifiDriver())

    def create_fan(self, name):
        return FanDevice(name, WifiDriver())


# ---------------- Factory Method ----------------
class DeviceFactory(ABC):
    @abstractmethod
    def create_device(self, name): ...     # the factory method

    @staticmethod
    def _default_driver():                 # Singleton used here
        return MqttDriver() if HomeConfig.get_instance().get("default_driver") == "mqtt" else WifiDriver()


class LightFactory(DeviceFactory):
    def create_device(self, name):
        return LightDevice(name, self._default_driver())


class FanFactory(DeviceFactory):
    def create_device(self, name):
        return FanDevice(name, self._default_driver())
