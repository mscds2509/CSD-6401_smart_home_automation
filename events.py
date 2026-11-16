"""(9) OBSERVER - sensors publish events, services subscribe."""
from abc import ABC, abstractmethod


class Observer(ABC):
    @abstractmethod
    def update(self, event: dict): ...


class Subject(ABC):
    @abstractmethod
    def subscribe(self, observer: Observer): ...

    @abstractmethod
    def unsubscribe(self, observer: Observer): ...

    @abstractmethod
    def notify(self, event: dict): ...


class MotionSensor(Subject):
    def __init__(self, location: str):
        self.location = location
        self._observers = []

    def subscribe(self, observer):
        self._observers.append(observer)

    def unsubscribe(self, observer):
        self._observers.remove(observer)

    def notify(self, event):
        for o in list(self._observers):
            o.update(event)

    def detect_motion(self):
        self.notify({"type": "motion", "location": self.location})
