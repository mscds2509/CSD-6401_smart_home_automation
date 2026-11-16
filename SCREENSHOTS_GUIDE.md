# Screenshot capture guide

The screenshots in `screenshots/` are the existing project reference images. To capture fresh, genuine screenshots of the updated running application:

1. Install the app dependencies and start the dashboard:
   ```bash
   python -m pip install -r requirements.txt
   python app.py
   ```
2. In a second Terminal window, install the optional screenshot dependency and browser:
   ```bash
   python -m pip install -r requirements-screenshots.txt
   python -m playwright install chromium
   ```
3. Run the capture script:
   ```bash
   python tools/capture_screenshots.py
   ```

The script signs in using `SMART_HOME_USER` / `SMART_HOME_PASSWORD` (defaults `admin` / `home1234`) and captures desktop overview, room bulk controls, automation, energy, settings, and mobile views into `screenshots/fresh/`. Set `CHROMIUM_PATH` if you want to use a locally installed Chromium executable. These images are captured from the actual Flask application and not generated mockups.

## Additional enhanced dashboard areas to capture
- **Automation:** include the Night Mode and Motion Security preset buttons, plus the energy-budget, time-window and long-running-device condition options.
- **Energy:** capture the Chart.js device energy doughnut chart and recent activity timeline.
- **Device architecture:** include cards with Wi-Fi/MQTT, Bridge, Legacy Adapter and Energy Decorator badges.
- **Command audit:** expand the Command Audit History disclosure and show the CSV/JSON export controls.

The bundled screenshot-capture utility captures a running, authenticated application. The static screenshot files already in `screenshots/` are retained as illustrative earlier figures; they should not be described as freshly captured after these additions until you run the capture utility against the updated application.


## Final build screenshot checklist

Capture these from the updated running app after starting Flask:
1. `01_dashboard_overview.png` — summary cards, room overview and active device states.
2. `02_room_controls.png` — room bulk ON/OFF and device brightness/fan speed controls.
3. `03_automation.png` — rule builder, presets and enabled/paused rules.
4. `04_energy_analytics.png` — current power doughnut, centre total, 7/30-day history and day comparison.
5. `05_activity_undo.png` — activity timeline, command audit, CSV/JSON export and undo.
6. `06_settings_page.png` — dedicated `/settings` page showing home, device and room settings.
7. `07_mobile_dashboard.png` — narrow mobile viewport with navigation and cards.

Do not use older reference screenshots as proof of newly added features. Re-capture after launching this exact build.
