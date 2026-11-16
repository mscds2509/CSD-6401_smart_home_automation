"""Capture genuine screenshots from a running SmartHome Flask dashboard.

Run the Flask app first, then execute this script. Optional environment variables:
SMART_HOME_URL, SMART_HOME_USER, SMART_HOME_PASSWORD, CHROMIUM_PATH.
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "screenshots" / "fresh"
OUT.mkdir(parents=True, exist_ok=True)
URL = os.getenv("SMART_HOME_URL", "http://127.0.0.1:5000")
USER = os.getenv("SMART_HOME_USER", "admin")
PASSWORD = os.getenv("SMART_HOME_PASSWORD", "home1234")

with sync_playwright() as p:
    launch = {"headless": True}
    executable = os.getenv("CHROMIUM_PATH")
    if executable:
        launch["executable_path"] = executable
    browser = p.chromium.launch(**launch)
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    page.goto(URL, wait_until="networkidle")
    if "/login" in page.url:
        page.fill('input[name="username"]', USER)
        page.fill('input[name="password"]', PASSWORD)
        page.locator('button[type="submit"]').click()
        page.wait_for_url("**/")
    page.wait_for_selector("#totalDevices")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / "01_dashboard_desktop.png"), full_page=True)
    for section, filename in [
        ("rooms", "02_rooms_and_bulk_controls.png"),
        ("automation", "03_automation_and_sensor_demo.png"),
        ("energy", "04_energy_insights.png"),
        ("settings", "05_settings_and_preferences.png"),
        ("activity", "06_activity_and_command_audit.png"),
    ]:
        page.locator(f"#{section}").scroll_into_view_if_needed()
        page.wait_for_timeout(350)
        page.screenshot(path=str(OUT / filename), full_page=False)
    page.goto(URL.rstrip("/") + "/settings", wait_until="networkidle")
    page.wait_for_selector("#homeSettingsForm")
    page.screenshot(path=str(OUT / "11_dedicated_settings_page.png"), full_page=True)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector("#commandHistoryPanel")
    page.locator("#commandHistoryPanel").scroll_into_view_if_needed()
    page.locator("#commandHistoryPanel").evaluate("el => el.open = true")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "07_command_audit_exports.png"), full_page=False)
    mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True)
    mobile.goto(URL, wait_until="networkidle")
    if "/login" in mobile.url:
        mobile.fill('input[name="username"]', USER)
        mobile.fill('input[name="password"]', PASSWORD)
        mobile.locator('button[type="submit"]').click()
        mobile.wait_for_url("**/")
    mobile.wait_for_selector("#totalDevices")
    mobile.wait_for_timeout(900)
    mobile.screenshot(path=str(OUT / "08_dashboard_mobile.png"), full_page=True)
    mobile.locator("#rooms").scroll_into_view_if_needed()
    mobile.screenshot(path=str(OUT / "09_room_controls_mobile.png"), full_page=False)
    mobile.locator("#automation").scroll_into_view_if_needed()
    mobile.screenshot(path=str(OUT / "10_automation_mobile.png"), full_page=False)
    browser.close()
print(f"Fresh live-app screenshots saved to: {OUT}")
