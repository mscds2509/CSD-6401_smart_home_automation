"""(8) FACADE - one simple API over DeviceManager, AutomationEngine, NotificationService, CommandInvoker."""
from config import HomeConfig
from commands import TurnOnCommand, TurnOffCommand


class HomeFacade:
    def __init__(self, devices, engine, notifier, invoker):
        self._config = HomeConfig.get_instance()
        self._devices, self._engine, self._notifier, self._invoker = devices, engine, notifier, invoker

    def turn_on_device(self, device_id):
        self._invoker.set_command(TurnOnCommand(self._devices.get_device(device_id)))
        self._invoker.execute_command()
        self._notifier.notify(f"{device_id} turned ON")

    def turn_off_device(self, device_id):
        self._invoker.set_command(TurnOffCommand(self._devices.get_device(device_id)))
        self._invoker.execute_command()
        self._notifier.notify(f"{device_id} turned OFF")

    def turn_off_all(self):
        for device_id in self._devices.get_all_devices():
            self.turn_off_device(device_id)

    def undo_last(self):
        self._invoker.undo()

    def get_notifications(self):
        return list(self._notifier.sent)

    def get_home_status(self):
        return {i: d.get_status() for i, d in self._devices.get_all_devices().items()}
