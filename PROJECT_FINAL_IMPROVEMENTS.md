# Final project enhancement notes

This update is an additive refinement of the existing Smart Home Automation project. The original ten GoF pattern modules and the existing CLI/web composition are retained.

## Added in this package

- Dedicated authenticated Settings page at `/settings`, with home preferences, device configuration and room comfort targets. The dashboard's existing settings section remains available.
- Premium visual refinement: clearer spacing, softer cards, stronger hierarchy, hover states and keyboard-visible focus styles.
- Room overview cards showing active-device counts, simulated temperature and humidity.
- Energy comparison KPIs for today versus yesterday, including percentage change where a yesterday baseline exists.
- Selectable 7-day and 30-day estimated energy history via `GET /api/energy?days=7|30`.
- Doughnut chart with device-specific colours, central live-watt total, percentage labels for larger slices, and tooltip values for every slice.
- Device cards show the persisted ON-since time when available.
- SQLite schema migration version tracking (`schema_migrations`) while retaining safe additive column checks.
- Safer session cookie defaults (`HttpOnly`, `SameSite=Lax`; enable `SMART_HOME_HTTPS=1` behind HTTPS).
- Additional energy-history range API validation test.

## Existing capabilities retained

The project continues to include room bulk controls, undo, manual/automatic modes, scenes, automation presets and conditions, activity/notification history, command audit CSV/JSON export, SQLite persistence, JSON state snapshot export, responsive dashboard styles, and the original pattern implementations.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. Demo credentials are `admin` / `home1234` unless `SMART_HOME_USER` and `SMART_HOME_PASSWORD` are set in the environment.

For a deployment, set a strong `SECRET_KEY`, change the demo credentials, serve only over HTTPS and set `SMART_HOME_HTTPS=1`. This is still a local educational prototype, not a production-ready home security controller.

## Tests

```bash
python -m unittest discover -s tests -v
```

The Flask integration tests require dependencies from `requirements.txt`. Do not count skipped tests as passed.

## Screenshot guidance

The screenshots already in `screenshots/` are retained as project reference images. They are not claimed to be freshly captured from this final build. To capture verified current screenshots, start the updated app and run the project's screenshot utility as described in `SCREENSHOTS_GUIDE.md`.
