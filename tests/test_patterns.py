import unittest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import HomeConfig
from factories import MqttFactory, WifiFactory, LightFactory
from devices.bridge import MqttDriver, WifiDriver, LightDevice
from devices.adapter import LegacyDeviceAdapter, LegacyVendorDevice
from devices.decorator import EnergyMonitoringDecorator
from commands import TurnOnCommand, CommandInvoker
from automation import AutomationRuleBuilder
from main import build_home


class T(unittest.TestCase):
    def setUp(self): HomeConfig._reset()

    def test_singleton(self):
        self.assertIs(HomeConfig.get_instance(), HomeConfig.get_instance())
        with self.assertRaises(RuntimeError): HomeConfig()

    def test_abstract_factory_families(self):
        self.assertIsInstance(MqttFactory().create_light("a")._driver, MqttDriver)
        self.assertIsInstance(WifiFactory().create_fan("b")._driver, WifiDriver)

    def test_factory_method_uses_config(self):
        HomeConfig.get_instance().set("default_driver", "mqtt")
        d = LightFactory().create_device("x")
        self.assertIsInstance(d, LightDevice); self.assertIsInstance(d._driver, MqttDriver)

    def test_adapter(self):
        a = LegacyDeviceAdapter("h", LegacyVendorDevice()); a.turn_on()
        self.assertEqual(a.get_status(), "h: ON")

    def test_decorator_energy(self):
        t = [0.0]; dev = EnergyMonitoringDecorator(LegacyDeviceAdapter("h", LegacyVendorDevice()), 1000, lambda: t[0])
        dev.turn_on(); t[0] = 3600; dev.turn_off()
        self.assertAlmostEqual(dev.get_energy_usage(), 1.0)

    def test_command_undo(self):
        dev = LegacyDeviceAdapter("h", LegacyVendorDevice()); inv = CommandInvoker()
        inv.set_command(TurnOnCommand(dev)); inv.execute_command()
        self.assertEqual(dev.get_status(), "h: ON"); inv.undo(); self.assertEqual(dev.get_status(), "h: OFF")

    def test_builder_validation(self):
        with self.assertRaises(ValueError): AutomationRuleBuilder().set_name("x").build()

    def test_full_flow_observer_rule_command(self):
        dash, facade, sensor = build_home()
        sensor.detect_motion()
        self.assertIn("ON", facade.get_home_status()["hall_light"])


if __name__ == "__main__":
    unittest.main()


class UiTests(unittest.TestCase):
    def setUp(self): HomeConfig._reset()

    def test_dashboard_api(self):
        dash, facade, sensor = build_home()
        dash.turn_on_device("fan"); dash.undo_last()
        self.assertTrue(dash.get_home_status()["fan"].endswith("OFF"))
        self.assertTrue(any("fan turned ON" in n for n in dash.get_notifications()))

import os
import tempfile
from pathlib import Path
import importlib.util

@unittest.skipUnless(importlib.util.find_spec('flask'), 'Install requirements.txt to run Flask integration tests')
class UpgradedAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as webapp
        cls.webapp = webapp

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.webapp.DB_PATH = Path(self.tmp.name) / "test.db"
        self.webapp.init_db()
        self.client = self.webapp.app.test_client()
        self.client.post("/login", data={"username":"admin","password":"home1234"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_dashboard_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Energy insights", response.data)

    def test_state_api_has_seed_devices(self):
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreaterEqual(payload["summary"]["total"], 6)

    def test_power_and_brightness_api(self):
        response = self.client.post("/api/device/kitchen_light/power", json={"on":True})
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/api/device/kitchen_light/setting",
                                    json={"field":"brightness","value":45})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["device"]["brightness"], 45)

    def test_create_rule(self):
        response = self.client.post("/api/rules", json={
            "name":"Test motion rule","trigger_type":"motion","device_id":"hall_light","action":"on"
        })
        self.assertEqual(response.status_code, 201)

    def test_scene(self):
        response = self.client.post("/api/scene/movie_mode")
        self.assertEqual(response.status_code, 200)

    def test_authentication(self):
        anonymous = self.webapp.app.test_client()
        response = anonymous.get("/api/state")
        self.assertEqual(response.status_code, 401)

class AdditionalPatternTests(unittest.TestCase):
    def setUp(self): HomeConfig._reset()

    def test_bridge_protocol_driver(self):
        light = LightDevice('bridge-test', MqttDriver())
        light.turn_on()
        self.assertIn('ON', light.get_status())

    def test_facade_exposes_simplified_control(self):
        _, facade, _ = build_home()
        facade.turn_on_device('hall_light')
        self.assertTrue(facade.get_home_status()['hall_light'].endswith('ON'))

    def test_observer_notifies_subscribers(self):
        from events import MotionSensor
        class Listener:
            def __init__(self): self.called = False
            def update(self, event): self.called = True
        sensor=MotionSensor('Test'); listener=Listener(); sensor.subscribe(listener)
        sensor.detect_motion(); self.assertTrue(listener.called)

    def test_factory_method_wifi_default(self):
        HomeConfig.get_instance().set('default_driver','wifi')
        self.assertIsInstance(LightFactory().create_device('x')._driver, WifiDriver)

class ExtendedApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import app as webapp
            cls.webapp=webapp
        except ModuleNotFoundError:
            raise unittest.SkipTest('Flask is required; install requirements.txt')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.webapp.DB_PATH=Path(self.tmp.name)/'extended.db'
        self.webapp.init_db()
        self.client=self.webapp.app.test_client()
        self.client.post('/login',data={'username':'admin','password':'home1234'})
    def tearDown(self): self.tmp.cleanup()
    def test_manual_mode_persists_and_sensor_api(self):
        r=self.client.post('/api/mode',json={'mode':'manual'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.get('/api/state').get_json()['mode'],'manual')
        self.assertTrue(self.client.get('/api/sensors').get_json())
    def test_energy_endpoint_has_daily_and_device_metrics(self):
        data=self.client.get('/api/energy').get_json()
        self.assertIn('today_kwh',data)
        self.assertIn('daily_kwh',data['device_breakdown'][0])
    def test_notifications_can_be_marked_read(self):
        state=self.client.get('/api/state').get_json()
        self.assertTrue(state['notifications'])
        notification_id=state['notifications'][0]['id']
        self.assertEqual(self.client.post(f'/api/notifications/{notification_id}/read').status_code,200)
    def test_invalid_power_payload_rejected(self):
        self.assertEqual(self.client.post('/api/device/fan/power',json={'on':'yes'}).status_code,400)
