"""Regression coverage for all ten patterns and the enhanced dashboard APIs."""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import HomeConfig
from factories import MqttFactory, WifiFactory, LightFactory, FanFactory
from devices.bridge import MqttDriver, WifiDriver, LightDevice, FanDevice
from devices.adapter import LegacyDeviceAdapter, LegacyVendorDevice
from devices.decorator import EnergyMonitoringDecorator
from commands import TurnOnCommand, TurnOffCommand, CommandInvoker
from automation import (AutomationRuleBuilder, EventTypeCondition, AutomationEngine, RuleDirector,
                         EnergyThresholdCondition, TimeWindowCondition, AnomalyCondition)
from repositories import CommandAuditRepository, TelemetryRepository
from state_store import StateSnapshotStore
from events import MotionSensor
from main import build_home


class AllPatternCoverage(unittest.TestCase):
    def setUp(self):
        HomeConfig._reset()

    def test_abstract_factory_creates_consistent_mqtt_and_wifi_families(self):
        for factory, driver in ((MqttFactory(), MqttDriver), (WifiFactory(), WifiDriver)):
            self.assertIsInstance(factory.create_light("L")._driver, driver)
            self.assertIsInstance(factory.create_fan("F")._driver, driver)

    def test_factory_method_selects_configured_driver_for_both_products(self):
        HomeConfig.get_instance().set("default_driver", "mqtt")
        self.assertIsInstance(LightFactory().create_device("L")._driver, MqttDriver)
        self.assertIsInstance(FanFactory().create_device("F")._driver, MqttDriver)

    def test_singleton_configuration_is_shared_and_mutable(self):
        first = HomeConfig.get_instance()
        first.set("home_name", "Test Home")
        self.assertIs(HomeConfig.get_instance(), first)
        self.assertEqual(HomeConfig.get_instance().get("home_name"), "Test Home")

    def test_builder_creates_enabled_rule_and_resets(self):
        dev = LegacyDeviceAdapter("lamp", LegacyVendorDevice())
        builder = AutomationRuleBuilder()
        rule = (builder.set_name("motion lamp").set_condition(EventTypeCondition("motion"))
                .add_action(TurnOnCommand(dev)).build())
        self.assertTrue(rule.evaluate({"type": "motion"}))
        rule.execute()
        self.assertEqual(dev.get_status(), "lamp: ON")
        with self.assertRaises(ValueError):
            builder.build()

    def test_adapter_translates_legacy_vendor_api(self):
        adapter = LegacyDeviceAdapter("legacy", LegacyVendorDevice())
        adapter.turn_on()
        self.assertEqual(adapter.get_status(), "legacy: ON")
        adapter.turn_off()
        self.assertEqual(adapter.get_status(), "legacy: OFF")

    def test_bridge_decouples_device_from_driver(self):
        light = LightDevice("bridge", MqttDriver())
        light.set_brightness(42)
        light.turn_on()
        self.assertEqual(light.get_status(), "bridge: ON")
        fan = FanDevice("bridge fan", WifiDriver())
        fan.set_speed(3)
        fan.turn_on()
        self.assertEqual(fan.get_status(), "bridge fan: ON")

    def test_decorator_accumulates_energy_without_changing_device(self):
        ticks = [0.0]
        device = EnergyMonitoringDecorator(LegacyDeviceAdapter("metered", LegacyVendorDevice()), 1000, lambda: ticks[0])
        device.turn_on(); ticks[0] = 1800; device.turn_off()
        self.assertAlmostEqual(device.get_energy_usage(), 0.5)

    def test_facade_coordinates_device_and_notification_services(self):
        dashboard, facade, _ = build_home()
        facade.turn_on_device("hall_light")
        self.assertTrue(facade.get_home_status()["hall_light"].endswith("ON"))
        self.assertTrue(any("hall_light turned ON" in item for item in facade.get_notifications()))

    def test_observer_subscribe_unsubscribe_and_notify(self):
        class Listener:
            def __init__(self): self.events = []
            def update(self, event): self.events.append(event)
        sensor, listener = MotionSensor("test room"), Listener()
        sensor.subscribe(listener); sensor.detect_motion()
        self.assertEqual(listener.events[0]["type"], "motion")
        sensor.unsubscribe(listener); sensor.detect_motion()
        self.assertEqual(len(listener.events), 1)

    def test_command_invoker_executes_and_undoes_both_commands(self):
        dev = LegacyDeviceAdapter("cmd", LegacyVendorDevice())
        invoker = CommandInvoker()
        invoker.set_command(TurnOnCommand(dev)); invoker.execute_command()
        self.assertEqual(dev.get_status(), "cmd: ON")
        invoker.undo(); self.assertEqual(dev.get_status(), "cmd: OFF")
        invoker.set_command(TurnOffCommand(dev)); invoker.execute_command()
        invoker.undo(); self.assertEqual(dev.get_status(), "cmd: ON")

    def test_automation_engine_observer_executes_built_rule(self):
        dev = LegacyDeviceAdapter("motion lamp", LegacyVendorDevice())
        engine, sensor = AutomationEngine(), MotionSensor("hall")
        rule = (AutomationRuleBuilder().set_name("lamp on motion")
                .set_condition(EventTypeCondition("motion")).add_action(TurnOnCommand(dev)).build())
        engine.add_rule(rule); sensor.subscribe(engine); sensor.detect_motion()
        self.assertEqual(dev.get_status(), "motion lamp: ON")

    def test_rule_director_builds_recipe(self):
        dev = LegacyDeviceAdapter("director lamp", LegacyVendorDevice())
        director = RuleDirector(AutomationRuleBuilder())
        rule = director.build_motion_rule(dev)
        self.assertEqual(rule.name, "motion-light")
        self.assertTrue(rule.evaluate({"type": "motion"}))
        night_rule = director.build_night_rule(dev)
        self.assertEqual(night_rule.name, "night-fan-off")
        self.assertTrue(night_rule.evaluate({"now": "23:30"}))


class StrategyAndRepositoryTests(unittest.TestCase):
    def test_energy_threshold_strategy(self):
        condition = EnergyThresholdCondition(2.5)
        self.assertFalse(condition.evaluate({"daily_kwh": 2.49}))
        self.assertTrue(condition.evaluate({"daily_kwh": 2.5}))

    def test_time_window_strategy_including_midnight_wrap(self):
        condition = TimeWindowCondition("23:00", "06:00")
        self.assertTrue(condition.evaluate({"now": "23:30"}))
        self.assertTrue(condition.evaluate({"now": "05:30"}))
        self.assertFalse(condition.evaluate({"now": "12:00"}))

    def test_anomaly_strategy(self):
        condition = AnomalyCondition(3600)
        self.assertFalse(condition.evaluate({"on_seconds": 3599}))
        self.assertTrue(condition.evaluate({"on_seconds": 3600}))

    def test_repository_persists_and_lists_command_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "repo.db"
            def connect():
                import sqlite3
                db = sqlite3.connect(db_path)
                db.row_factory = sqlite3.Row
                return db
            with connect() as db:
                db.execute("CREATE TABLE command_audit(id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, device_name TEXT, action TEXT, source TEXT, created_at TEXT, command_group TEXT)")
            repo = CommandAuditRepository(connect)
            repo.add(device_id="lamp", device_name="Lamp", action="ON", source="test", created_at="2026-01-01T10:00:00+00:00")
            self.assertEqual(repo.list_recent()[0]["device_name"], "Lamp")

    def test_state_snapshot_store_round_trips_versioned_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = StateSnapshotStore(Path(tmp) / "state.json")
            original = {"schema_version": 1, "settings": {"home_name": "Demo"}, "automation_rules": []}
            store.save(original)
            self.assertEqual(store.load()["settings"]["home_name"], "Demo")

    def test_telemetry_repository_records_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "telemetry.db"
            def connect():
                import sqlite3
                db = sqlite3.connect(db_path)
                db.row_factory = sqlite3.Row
                return db
            with connect() as db:
                db.execute("CREATE TABLE energy_samples(id INTEGER PRIMARY KEY, device_id TEXT, watts REAL, sampled_at TEXT)")
            repo = TelemetryRepository(connect)
            repo.record_power_sample("__home__", 125.5, "2026-01-01T10:00:00+00:00")
            with connect() as db:
                self.assertEqual(db.execute("SELECT watts FROM energy_samples").fetchone()[0], 125.5)


@unittest.skipUnless(importlib.util.find_spec("flask"), "Install requirements.txt to run Flask API integration tests")
class EnhancedDashboardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SMART_HOME_DISABLE_SCHEDULER"] = "1"
        import app as webapp
        cls.webapp = webapp

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.webapp.DB_PATH = Path(self.tmp.name) / "dashboard-test.db"
        self.webapp.init_db()
        self.client = self.webapp.app.test_client()
        self.client.post("/login", data={"username": "admin", "password": "home1234"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_settings_page_and_navigation_render(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Home settings", response.data)
        self.assertIn(b"Undo last command", response.data)

    def test_room_bulk_control_and_undo(self):
        before = {d["id"]: d["is_on"] for d in self.webapp.dashboard_state()["devices"] if d["room"] == "Living Room"}
        response = self.client.post("/api/rooms/power", json={"room": "Living Room", "on": True})
        self.assertEqual(response.status_code, 200)
        living = [d for d in response.get_json()["devices"] if d["room"] == "Living Room"]
        self.assertTrue(living and all(d["is_on"] for d in living))
        undone = self.client.post("/api/undo", json={})
        self.assertEqual(undone.status_code, 200)
        after = {d["id"]: d["is_on"] for d in undone.get_json()["devices"] if d["room"] == "Living Room"}
        self.assertEqual(after, before)

    def test_device_and_room_preferences_are_persisted(self):
        response = self.client.patch("/api/device/hall_light/config", json={"name": "Entry Lamp", "room": "Entry", "watts": 14})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["device"]["name"], "Entry Lamp")
        response = self.client.patch("/api/rooms/config", json={"room": "Entry", "name": "Entrance", "target_temperature": 21.5, "target_humidity": 42, "notes": "Keep clear"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(r["room"] == "Entrance" for r in response.get_json()["room_preferences"]))

    def test_automation_accepts_advanced_trigger_and_toggle_action(self):
        response = self.client.post("/api/rules", json={"name": "Door toggle", "trigger_type": "door_open", "device_id": "hall_light", "action": "toggle"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.post("/api/trigger", json={"trigger_type": "door_open"}).status_code, 200)

    def test_manual_mode_pauses_automatic_trigger(self):
        self.client.post("/api/mode", json={"mode": "manual"})
        before = self.webapp.device_row("hall_light")["is_on"]
        self.client.post("/api/trigger", json={"trigger_type": "motion"})
        self.assertEqual(self.webapp.device_row("hall_light")["is_on"], before)

    def test_invalid_payloads_return_client_errors_not_server_errors(self):
        cases = [
            ("post", "/api/device/hall_light/power", ["not", "object"]),
            ("post", "/api/device/missing/power", {"on": True}),
            ("post", "/api/mode", {"mode": "turbo"}),
            ("post", "/api/settings", {"home_name": 123}),
            ("post", "/api/rooms/power", {"room": "Unknown", "on": True}),
            ("post", "/api/trigger", {"trigger_type": "unknown"}),
            ("patch", "/api/device/hall_light/config", {"watts": 9000}),
            ("patch", "/api/rooms/config", {"room": "Hallway", "target_temperature": 90}),
            ("post", "/api/rules", {"name": "bad", "trigger_type": "time", "device_id": "hall_light", "action": "on", "schedule_time": "25:99"}),
        ]
        for method, path, payload in cases:
            response = getattr(self.client, method)(path, json=payload)
            self.assertGreaterEqual(response.status_code, 400, (method, path))
            self.assertLess(response.status_code, 500, (method, path))

    def test_missing_undo_and_unknown_resources_are_handled(self):
        self.assertEqual(self.client.post("/api/undo", json={}).status_code, 409)
        self.assertEqual(self.client.patch("/api/device/unknown/config", json={"name": "x"}).status_code, 404)
        self.assertEqual(self.client.post("/api/notifications/99999/read").status_code, 404)

    def test_strategy_automation_rules_and_command_audit_exports(self):
        for payload in (
            {"name":"Budget rule","trigger_type":"energy_threshold","device_id":"hall_light","action":"off","threshold":0.5},
            {"name":"Night window","trigger_type":"time_window","device_id":"fan","action":"off","window_start":"23:00","window_end":"06:00"},
            {"name":"Long-running device","trigger_type":"anomaly","device_id":"hall_light","action":"off","duration_seconds":3600},
        ):
            response = self.client.post("/api/rules", json=payload)
            self.assertEqual(response.status_code, 201, response.get_json())
        self.client.post("/api/device/hall_light/power", json={"on": True})
        commands = self.client.get("/api/commands")
        self.assertEqual(commands.status_code, 200)
        self.assertTrue(commands.get_json()["commands"])
        self.assertEqual(self.client.get("/api/commands/export?format=csv").status_code, 200)
        self.assertEqual(self.client.get("/api/commands/export?format=json").status_code, 200)

    def test_energy_history_range_validation(self):
        self.assertEqual(self.client.get("/api/energy?days=7").status_code, 200)
        self.assertEqual(self.client.get("/api/energy?days=30").status_code, 200)
        self.assertEqual(self.client.get("/api/energy?days=14").status_code, 400)
        self.assertEqual(self.client.get("/api/energy?days=abc").status_code, 400)

    def test_state_snapshot_endpoint_returns_json_download(self):
        response = self.client.get("/api/state/snapshot")
        self.assertEqual(response.status_code, 200)
        self.assertIn("smart-home-state.json", response.headers.get("Content-Disposition", ""))
        self.assertEqual(response.get_json()["schema_version"], 1)

    def test_automation_presets_are_available(self):
        self.assertEqual(self.client.post("/api/rules/preset/night_mode").status_code, 201)
        self.assertEqual(self.client.post("/api/rules/preset/motion_security").status_code, 201)
        with self.webapp.connect() as db:
            night = db.execute("SELECT trigger_type,window_start,window_end FROM rules WHERE name LIKE 'Night Mode%' ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual((night["trigger_type"], night["window_start"], night["window_end"]), ("time_window", "23:00", "06:00"))

    def test_invalid_strategy_parameters_are_rejected(self):
        response = self.client.post("/api/rules", json={"name":"Bad budget","trigger_type":"energy_threshold","device_id":"hall_light","action":"off","threshold":0})
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/rules", json={"name":"Bad window","trigger_type":"time_window","device_id":"fan","action":"off","window_start":"25:99","window_end":"06:00"})
        self.assertEqual(response.status_code, 400)



if __name__ == "__main__":
    unittest.main()
