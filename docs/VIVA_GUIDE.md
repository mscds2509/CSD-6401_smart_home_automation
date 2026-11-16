# Smart Home Automation — Viva Preparation

## Project summary
A Flask and SQLite-based smart-home software simulation. It demonstrates device control, room grouping, scenes, event-driven automation, estimated energy analytics, room environment simulation, notifications, and persistent operating mode. No physical IoT hardware or calibrated meter is connected.

## Architecture
- `app.py`: Flask routes, SQLite persistence, scheduler, dashboard state, simulation services.
- `main.py`: composition root wiring the design-pattern-backed objects.
- `facade.py`, `commands.py`, `events.py`, `automation.py`, `services.py`: application behavior.
- `factories.py`, `devices/`: device creation and device abstractions.
- `config.py`: singleton configuration.
- `templates/`, `static/`: responsive web interface.

## Design patterns demonstrated
1. Singleton — `HomeConfig` provides one shared configuration instance.
2. Factory Method — `LightFactory` creates configured devices.
3. Abstract Factory — MQTT/Wi-Fi factories create compatible device families.
4. Builder — `AutomationRuleBuilder` assembles automation rules.
5. Adapter — `LegacyDeviceAdapter` adapts a legacy vendor device.
6. Bridge — device abstractions delegate operations to protocol drivers.
7. Decorator — `EnergyMonitoringDecorator` adds energy tracking behavior.
8. Facade — `HomeFacade` offers a simplified home-control API.
9. Observer — motion events notify subscribed automation and notification services.
10. Command — turn-on/off commands support execution and undo.

## Common viva questions
**Why Flask?** It is lightweight and provides routing, request handling, templates, and JSON APIs without a heavyweight framework.

**Why SQLite?** It is embedded, requires no separate database server, and is suitable for a local academic prototype.

**What is manual mode?** Manual mode suppresses automatic trigger execution while allowing direct user device controls. Automatic mode enables scheduled and motion-triggered rules.

**How is energy calculated?** The simulation accumulates configured device watts × elapsed hours / 1000. The result is an estimate, not a physical meter reading.

**How are temperature and humidity obtained?** The application simulates bounded room-level values with small random drift; there are no real sensors.

**What is the purpose of the Facade?** It hides the complexity of managers, commands, and device operations behind a simple interface.

**How does undo work?** The Command pattern retains the last command and invokes its inverse operation.

**What happens when the server stops?** Persistent data remains in SQLite. The elapsed-time energy calculation is bounded to avoid assigning an unreasonably large interval after downtime.

**What are the limitations?** Values are simulated, authentication is a simple local demo login, and production deployment would require stronger credential management, CSRF protection, authorization, database migration strategy, and real hardware integrations.

## Demo flow
1. Sign in using configured credentials.
2. Switch between Automatic and Manual and explain the difference.
3. Toggle a light/fan and adjust brightness/speed.
4. Activate a scene.
5. Create a motion or scheduled rule and test motion in Automatic mode.
6. Inspect room temperature/humidity and energy estimates.
7. Open notifications and mark one or all as read.
8. Explain the class and sequence diagrams in `docs/`.

## New enhancement demonstration (updated build)
1. Open **Settings** and change the home name. Show that the dashboard header updates.
2. Select **Manual** mode. Use the Automation sensor demo buttons (Motion / Door / Temperature / Humidity). Explain that events are logged but automatic rules are paused. Toggle a device manually to show direct control remains available.
3. Switch to **Automatic** mode and trigger Motion or Door again. Show an enabled matching rule operating its selected device.
4. In **Rooms & devices**, use **All ON** / **All OFF** on one room to demonstrate bulk control.
5. Switch a device and use **Undo last command** in the header. Explain the persisted undo stack.
6. In **Settings**, edit a device's display name / room / wattage, then set room comfort targets and notes. Explain that these are software configuration values, not hardware commands.
7. Use the screenshot utility to capture the actual running desktop and mobile dashboard.

### New validation points for viva
- Power payloads require a boolean `on` field.
- Device wattage is bounded from 0 to 5000 W; device labels and room names have length limits.
- Room comfort targets are constrained to 10–35°C and 20–80% humidity.
- Unsupported triggers, malformed schedules, unknown devices/rooms and an empty undo stack return client error responses instead of an unhandled server error.
- Sensor triggers and energy/environment readings are simulated. This prototype does not connect to physical sensors, relays or a real energy meter.

## Additional architecture upgrades

- **Repository / DAO:** `CommandAuditRepository` and `TelemetryRepository` encapsulate SQL access behind methods and accept a connection factory, which makes persistence testable.
- **Strategy:** `EnergyThresholdCondition` checks daily kWh, `TimeWindowCondition` handles local-time ranges including midnight rollover, and `AnomalyCondition` detects devices that remain ON beyond a configured duration.
- **Background worker:** every 10 seconds the simulation worker advances sensor/energy data and evaluates energy-budget, time-window and anomaly rules. Explain that this is a local prototype worker, not a production scheduler.
- **Audit export:** every device power change is written to the command audit table and can be inspected in the Activity section or exported as CSV/JSON.
- **Dashboard observability:** device badges expose Bridge/protocol, Legacy Adapter and Energy Decorator composition; Chart.js presents energy distribution and recent activity frequency.
- **Presets:** Night Mode creates a scheduled fan-off rule at 23:00; Motion Security creates a motion-triggered hall-light-on rule.

## Suggested live viva sequence
1. Switch to Manual mode and simulate motion; show that the event is logged without automatic device action.
2. Switch to Automatic mode and simulate motion; show the hall-light rule executing.
3. Add a Night Mode or Motion Security preset and pause/enable it.
4. Create an energy threshold or anomaly rule and explain its Strategy condition.
5. Toggle a device, open Command Audit History, undo the last command, and download CSV/JSON.
6. Point to Wi-Fi/MQTT Bridge, Legacy Adapter and Energy Decorator badges on device cards.

- **JSON state memento:** `StateSnapshotStore` writes a versioned snapshot of home settings, device configuration and automation-rule state to `instance/state.json`. SQLite remains the live source of truth; the JSON snapshot is an export/backup artifact.
