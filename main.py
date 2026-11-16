"""Composition root + demo. Run:  python main.py"""
from config import HomeConfig
from factories import MqttFactory, LightFactory, FanFactory
from devices.adapter import LegacyDeviceAdapter, LegacyVendorDevice
from devices.decorator import EnergyMonitoringDecorator
from events import MotionSensor
from automation import AutomationEngine, AutomationRuleBuilder, RuleDirector
from services import NotificationService, DeviceManager
from commands import CommandInvoker
from facade import HomeFacade


class Dashboard:                          # the client: only talks to the Facade
    def __init__(self, facade):
        self._f = facade

    def turn_on_device(self, device_id): self._f.turn_on_device(device_id)
    def turn_off_device(self, device_id): self._f.turn_off_device(device_id)
    def turn_off_all(self): self._f.turn_off_all()
    def undo_last(self): self._f.undo_last()
    def get_home_status(self): return self._f.get_home_status()
    def get_notifications(self): return self._f.get_notifications()


def build_home():
    HomeConfig.get_instance().set("default_driver", "wifi")           # Singleton
    dm = DeviceManager()
    dm.register("hall_light", LightFactory().create_device("Hall light"))          # Factory Method
    dm.register("fan", EnergyMonitoringDecorator(FanFactory().create_device("Fan")))  # Decorator
    dm.register("bedroom_light", MqttFactory().create_light("Bedroom light"))      # Abstract Factory
    dm.register("old_heater", LegacyDeviceAdapter("Old heater", LegacyVendorDevice()))  # Adapter
    engine, notifier, invoker = AutomationEngine(), NotificationService(), CommandInvoker()
    engine.add_rule(RuleDirector(AutomationRuleBuilder()).build_motion_rule(dm.get_device("hall_light")))  # Builder
    sensor = MotionSensor("Hallway")
    sensor.subscribe(engine); sensor.subscribe(notifier)                           # Observer
    facade = HomeFacade(dm, engine, notifier, invoker)
    return Dashboard(facade), facade, sensor


if __name__ == "__main__":
    dash, facade, sensor = build_home()
    print("1) Dashboard -> Facade -> Command"); dash.turn_on_device("fan")
    print("2) Motion sensor -> Observers -> Rule -> Command"); sensor.detect_motion()
    print("3) Status:", dash.get_home_status())
    print("4) Undo last command"); facade.undo_last()
    print("5) Turn everything off"); dash.turn_off_all()
    print("6) Status:", dash.get_home_status())
