from events import Observer


class NotificationService(Observer):      # ConcreteObserver
    def __init__(self):
        self.sent = []

    def notify(self, message):
        self.sent.append(message)
        print(f"   [notify] {message}")

    def update(self, event):
        self.notify(f"{event['type']} detected at {event.get('location', '?')}")


class DeviceManager:
    def __init__(self):
        self._devices = {}

    def register(self, device_id, device):
        self._devices[device_id] = device

    def get_device(self, device_id):
        return self._devices[device_id]

    def get_all_devices(self):
        return dict(self._devices)
