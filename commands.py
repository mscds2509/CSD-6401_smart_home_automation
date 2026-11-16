"""(10) COMMAND - requests as objects, with undo history."""
from abc import ABC, abstractmethod


class Command(ABC):
    @abstractmethod
    def execute(self): ...

    @abstractmethod
    def undo(self): ...


class TurnOnCommand(Command):
    def __init__(self, device):
        self._device = device

    def execute(self):
        self._device.turn_on()

    def undo(self):
        self._device.turn_off()


class TurnOffCommand(Command):
    def __init__(self, device):
        self._device = device

    def execute(self):
        self._device.turn_off()

    def undo(self):
        self._device.turn_on()


class CommandInvoker:
    def __init__(self):
        self._command = None
        self._history = []

    def set_command(self, command: Command):
        self._command = command

    def execute_command(self):
        if self._command:
            self._command.execute()
            self._history.append(self._command)

    def undo(self):
        if self._history:
            self._history.pop().undo()
