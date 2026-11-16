"""(2) BUILDER (+Director) for rules, and the AutomationEngine (an Observer)."""
from abc import ABC, abstractmethod
from datetime import datetime, time
from config import HomeConfig
from commands import Command, TurnOnCommand, TurnOffCommand
from events import Observer


class Condition(ABC):
    @abstractmethod
    def evaluate(self, event: dict) -> bool: ...


class EventTypeCondition(Condition):
    def __init__(self, event_type):
        self._type = event_type

    def evaluate(self, event):
        return event.get("type") == self._type


class EnergyThresholdCondition(Condition):
    """Strategy: true when the home daily energy reaches a kWh budget."""
    def __init__(self, threshold_kwh: float):
        if threshold_kwh <= 0:
            raise ValueError("Energy threshold must be greater than zero")
        self.threshold_kwh = float(threshold_kwh)

    def evaluate(self, event):
        return float(event.get("daily_kwh", 0)) >= self.threshold_kwh


class TimeWindowCondition(Condition):
    """Strategy: supports both ordinary and overnight local-time windows."""
    def __init__(self, start: str, end: str):
        self.start = time.fromisoformat(start)
        self.end = time.fromisoformat(end)

    def evaluate(self, event):
        value = event.get("now")
        if value is None:
            value = datetime.now().time()
        elif isinstance(value, datetime):
            value = value.time()
        elif isinstance(value, str):
            value = time.fromisoformat(value)
        if self.start <= self.end:
            return self.start <= value <= self.end
        return value >= self.start or value <= self.end


class AnomalyCondition(Condition):
    """Strategy: true when a device has remained ON beyond a duration limit."""
    def __init__(self, max_on_seconds: int):
        if int(max_on_seconds) <= 0:
            raise ValueError("Anomaly duration must be greater than zero")
        self.max_on_seconds = int(max_on_seconds)

    def evaluate(self, event):
        return float(event.get("on_seconds", 0)) >= self.max_on_seconds


class AutomationRule:                     # Product
    def __init__(self, name, condition, actions, enabled=True):
        self.name, self.condition, self.actions, self.enabled = name, condition, actions, enabled

    def evaluate(self, event) -> bool:
        return self.enabled and self.condition.evaluate(event)

    def execute(self):
        for action in self.actions:       # actions are Commands
            action.execute()


class AutomationRuleBuilder:              # Builder (fluent)
    def __init__(self):
        self.reset()

    def reset(self):
        self._name, self._condition, self._actions, self._enabled = None, None, [], True
        return self

    def set_name(self, name):
        self._name = name; return self

    def set_condition(self, condition: Condition):
        self._condition = condition; return self

    def add_action(self, action: Command):
        self._actions.append(action); return self

    def set_enabled(self, enabled: bool):
        self._enabled = enabled; return self

    def build(self) -> AutomationRule:
        if not (self._name and self._condition and self._actions):
            raise ValueError("A rule needs a name, a condition and at least one action")
        rule = AutomationRule(self._name, self._condition, list(self._actions), self._enabled)
        self.reset()
        return rule


class RuleDirector:                       # Director: knows READY-MADE recipes
    def __init__(self, builder: AutomationRuleBuilder):
        self._b = builder

    def build_motion_rule(self, light):
        return (self._b.set_name("motion-light").set_condition(EventTypeCondition("motion"))
                .add_action(TurnOnCommand(light)).build())

    def build_night_rule(self, fan):
        return (self._b.set_name("night-fan-off").set_condition(TimeWindowCondition("23:00", "06:00"))
                .add_action(TurnOffCommand(fan)).build())


class AutomationEngine(Observer):         # ConcreteObserver
    def __init__(self):
        self._config = HomeConfig.get_instance()
        self._rules = []

    def add_rule(self, rule):
        self._rules.append(rule)

    def enable_rule(self, name):
        for r in self._rules:
            if r.name == name:
                r.enabled = True

    def process_event(self, event):
        for r in self._rules:
            if r.evaluate(event):
                print(f"   [engine] rule '{r.name}' fired")
                r.execute()

    def update(self, event):
        self.process_event(event)
