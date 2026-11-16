from abc import ABC, abstractmethod


class SmartDevice(ABC):
    """Shared interface (Target of Adapter, Component of Decorator, Receiver of Command)."""

    @abstractmethod
    def turn_on(self): ...

    @abstractmethod
    def turn_off(self): ...

    @abstractmethod
    def get_status(self) -> str: ...
