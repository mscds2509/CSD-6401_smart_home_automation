# Smart Home Automation System

A software-only Smart Home Automation System built with Python, Flask, SQLite, HTML, CSS and JavaScript. It demonstrates the 10 original requested GoF patterns, plus Strategy-based automation conditions and a Repository / DAO persistence boundary.

## Features
- Responsive dashboard with overview cards and room-wise device controls
- Simulated lights, fans and legacy heater
- Brightness and fan-speed controls
- Motion sensor simulation and rule-based automation
- Scheduled automation rules (server must remain running)
- Scenes: Good Morning, Movie Mode, Away Mode and Relax Mode
- Estimated energy monitoring and device load breakdown
- Activity log and notifications
- SQLite persistence for devices, rules, settings and events
- Login/logout and JSON API
- Unit tests for the design patterns and API

## Requirements
- Python 3.10+
- pip

## Setup (Windows PowerShell)
```powershell
cd smart_home_upgraded
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

## Setup (macOS/Linux)
```bash
cd smart_home_upgraded
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

Demo login:
- Username: `admin`
- Password: `home1234`

Change credentials before sharing or deploying:
- Windows PowerShell: `$env:SMART_HOME_USER="youruser"; $env:SMART_HOME_PASSWORD="your-strong-password"; $env:SECRET_KEY="a-long-random-secret"`
- macOS/Linux: `export SMART_HOME_USER="youruser"` and set `SMART_HOME_PASSWORD` and `SECRET_KEY`.

## Run tests
```bash
python -m unittest discover -s tests -v
```

## Run the original pattern demonstration
```bash
python main.py
```

## API endpoints
- `GET /api/state`
- `POST /api/device/<device_id>/power` JSON: `{"on": true}`
- `POST /api/device/<device_id>/setting` JSON: `{"field":"brightness","value":60}`
- `POST /api/motion`
- `POST /api/all-off`
- `POST /api/undo`
- `POST /api/scene/<scene_id>`
- `POST /api/rules`
- `PATCH /api/rules/<id>`
- `DELETE /api/rules/<id>`
- `GET /api/export`
- `GET /health`

## Design patterns
1. Factory Method — `factories.py`
2. Abstract Factory — `factories.py`
3. Builder — `automation.py`
4. Singleton — `config.py`
5. Adapter — `devices/adapter.py`
6. Bridge — `devices/bridge.py`
7. Decorator — `devices/decorator.py`
8. Facade — `facade.py`
9. Observer — `events.py`, `automation.py`, `services.py`
10. Command — `commands.py`

## Notes
- All hardware is simulated in Python; no physical devices are required.
- Energy is an estimate derived from configured wattage and device state, not a real electricity meter.
- The scheduler checks scheduled rules while the Flask process is running. For production, use a dedicated scheduler and proper authentication, CSRF protection, HTTPS and environment-managed secrets.


## Refined UI and report screenshots
- The dashboard uses a refined visual layer with consistent spacing, typography, rounded cards, restrained shadows, clearer navigation states and responsive mobile spacing.
- Numbered, captioned report/viva figures are in `screenshots/`.
- See `SCREENSHOTS_GUIDE.md` for figure captions, recommended report placement and instructions for recapturing screenshots from a live run.
- Screenshot values are representative demo values. This project is a software simulation; no physical devices or live electricity meter are connected.

## Extended simulation capabilities
- **Manual / Automatic mode:** Automatic mode evaluates motion and scheduled rules. Manual mode suppresses trigger-driven actions while keeping dashboard controls available. The selected mode is stored in SQLite.
- **Room environment:** Room temperature and humidity values are simulated with bounded drift. These are not physical sensor readings.
- **Energy analytics:** The app accumulates estimated kWh from configured watts and elapsed time, including a daily home total and per-device daily estimates. Values are estimates, not utility-meter measurements.
- **Notifications:** Events are also stored in a notification center with unread counts and mark-read / mark-all-read actions.

Additional API routes:
- `POST /api/mode` JSON: `{"mode":"manual"}` or `{"mode":"automatic"}`
- `GET /api/energy`
- `GET /api/sensors`
- `POST /api/notifications/<id>/read`
- `POST /api/notifications/read-all`

UML and viva material: `docs/uml_class_diagram.mmd`, `docs/uml_sequence_diagram.mmd`, and `docs/VIVA_GUIDE.md`. Mermaid source files can be rendered in Mermaid-compatible Markdown tools. Existing screenshot files and their guide are retained; their values are representative rather than a fresh capture of a running browser session.

### Quick start on macOS (MacBook)
```bash
cd ~/Downloads/smart_home_upgraded
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```
Then open `http://127.0.0.1:5000` in your browser. If a virtual environment is already active, you can skip the first two commands. The app entry point is `python app.py` (not `python web.py`).

## Added controls and configuration
- **Settings page:** change the home display name, switch Manual / Automatic operation, rename devices, move devices between rooms, and update their configured wattage.
- **Room bulk controls:** switch all devices in a room ON or OFF from the room header.
- **Undo last command:** the dashboard exposes an Undo button. The last device power action is persisted in SQLite; room and scene operations are grouped so one Undo restores the entire action.
- **Room comfort preferences:** rename rooms and save target temperature, target humidity and notes. Targets are configuration values; the environment readings remain simulated.
- **Expanded automation:** supported triggers are motion, door-open, high-temperature, high-humidity and scheduled time. Actions are Turn ON, Turn OFF and Toggle. Sensor trigger buttons in the Automation section let you demonstrate each event.
- **Manual / Automatic demonstration:** the overview displays a mode banner. In Manual mode, simulated sensor events are logged but do not execute database automation rules. Switch to Automatic to enable them again.
- **API validation:** JSON object validation, range checks, resource-not-found responses and invalid-trigger/action handling are included.

New API routes:
- `POST /api/rooms/power` JSON: `{"room":"Living Room","on":true}`
- `PATCH /api/device/<device_id>/config` JSON: `{"name":"Entry Light","room":"Hallway","watts":12}`
- `PATCH /api/rooms/config` JSON: `{"room":"Hallway","name":"Entry","target_temperature":22,"target_humidity":45,"notes":""}`
- `POST /api/trigger` JSON: `{"trigger_type":"door_open"}` (also `motion`, `temperature_high`, `humidity_high`)

## Fresh screenshot capture
The capture utility in `tools/capture_screenshots.py` takes real screenshots from a running, authenticated Flask app. Install the optional dependency with `python -m pip install -r requirements-screenshots.txt`, install Chromium with `python -m playwright install chromium`, start the app, then run `python tools/capture_screenshots.py`. Output is written to `screenshots/fresh/`. See `SCREENSHOTS_GUIDE.md`.

## Test coverage notes
`tests/test_improvements.py` adds focused tests for each of the ten design patterns, the rule director, and integration cases for the new endpoints and validation. Flask API integration tests are skipped automatically when Flask is not installed; install `requirements.txt` before running the full suite.

## Data-driven automation and observability (enhanced)
- **Repository / DAO layer:** `repositories.py` provides `CommandAuditRepository` and `TelemetryRepository`. SQL for audit and sample persistence is isolated behind repository methods.
- **Strategy-based conditions:** `automation.py` includes `EnergyThresholdCondition`, `TimeWindowCondition` and `AnomalyCondition`. Rules can respond to a daily kWh budget, a local-time window (including windows crossing midnight), or a device remaining ON beyond a configured duration.
- **Background simulation worker:** a daemon worker periodically advances simulated room readings and energy estimates, and evaluates data-driven conditions. It is for local demonstration only; production deployments should use a supervised worker/scheduler.
- **Command audit:** state changes are written to `command_audit`. Authenticated endpoints expose recent commands and downloadable CSV/JSON exports.
- **JSON state memento:** `state_store.py` writes a versioned `instance/state.json` backup of home settings, device configuration and automation-rule state. SQLite remains the live source of truth; the JSON file is a portable snapshot.
- **Dashboard observability:** protocol / Bridge, Legacy Adapter and Energy Decorator badges are shown on device cards. Chart.js renders a device energy breakdown and recent activity timeline. Dashboard refresh polling runs every 2.5 seconds.
- **Automation presets:** the Automation section includes Night Mode and Motion Security one-click presets.

Additional API routes:
- `GET /api/state/snapshot` — download a versioned JSON state snapshot
- `GET /api/commands` — recent command audit records
- `GET /api/commands/export?format=csv` — CSV audit download
- `GET /api/commands/export?format=json` — JSON audit download
- `POST /api/rules/preset/night_mode`
- `POST /api/rules/preset/motion_security`

Advanced rule payload examples:
```json
{"name":"Energy budget","trigger_type":"energy_threshold","device_id":"fan","action":"off","threshold":2.5}
```
```json
{"name":"Night window","trigger_type":"time_window","device_id":"fan","action":"off","window_start":"23:00","window_end":"06:00"}
```
```json
{"name":"Long-running light","trigger_type":"anomaly","device_id":"hall_light","action":"off","duration_seconds":3600}
```

The additional Strategy condition classes and JSON snapshot utility are covered by unit tests. See `docs/ARCHITECTURE_DECISIONS.md` for Architecture Decision Records covering Bridge, Decorator, Repository/DAO and Strategy.


## Final dashboard refinement (November 2026)

The latest refinement adds a dedicated `/settings` page, room overview cards with active-device and simulated climate summaries, today-vs-yesterday energy comparison, selectable 7/30-day energy history, an improved colour-coded doughnut chart, ON-since status hints, SQLite schema version tracking and safer session-cookie defaults. See `PROJECT_FINAL_IMPROVEMENTS.md` for the exact scope and run instructions.

For HTTPS deployments set `SMART_HOME_HTTPS=1`, configure a strong `SECRET_KEY`, and replace the demo credentials with `SMART_HOME_USER` / `SMART_HOME_PASSWORD`. The project remains an educational simulation; power and energy figures are estimates, not certified meter readings.
