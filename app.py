"""Smart Home Automation System - Flask dashboard with SQLite persistence."""
from __future__ import annotations

import json
import csv
import io
import os
import sqlite3
import threading
import time
import random
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, session, url_for, flash, Response

from main import build_home
from config import HomeConfig
from automation import EnergyThresholdCondition, TimeWindowCondition, AnomalyCondition, AutomationRuleBuilder, RuleDirector
from repositories import CommandAuditRepository, TelemetryRepository
from state_store import StateSnapshotStore

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("SMART_HOME_DB", BASE_DIR / "instance" / "smart_home.db"))
STATE_SNAPSHOT_PATH = Path(os.environ.get("SMART_HOME_STATE_FILE", BASE_DIR / "instance" / "state.json"))
STATE_STORE = StateSnapshotStore(STATE_SNAPSHOT_PATH)
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-secret")
app.config["JSON_SORT_KEYS"] = False
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SMART_HOME_HTTPS", "0") == "1",
)

# The original project composition root supplies the Facade, Commands, Observer,
# Builder, factories, adapters, bridge and decorator implementations.
DASHBOARD, HOME_FACADE, MOTION_SENSOR = build_home()
STATE_LOCK = threading.RLock()

SEED_DEVICES = [
    ("hall_light", "Hall Light", "light", "Hallway", 12, 100, 0, "Wi-Fi"),
    ("fan", "Living Room Fan", "fan", "Living Room", 65, 0, 1, "Wi-Fi"),
    ("bedroom_light", "Bedroom Light", "light", "Bedroom", 10, 75, 0, "MQTT"),
    ("old_heater", "Legacy Heater", "heater", "Bedroom", 1200, 0, 0, "Legacy adapter"),
    ("kitchen_light", "Kitchen Light", "light", "Kitchen", 10, 100, 0, "Wi-Fi"),
    ("hall_fan", "Hall Fan", "fan", "Hallway", 55, 0, 0, "MQTT"),
]
SCENES = {
    "good_morning": {"label": "Good Morning", "description": "Brighten the home and start the day.",
                     "devices": {"hall_light": True, "bedroom_light": True, "kitchen_light": True, "fan": False}},
    "movie_mode": {"label": "Movie Mode", "description": "Dim the living area and quiet the room.",
                   "devices": {"hall_light": False, "bedroom_light": False, "kitchen_light": False, "fan": False}},
    "away_mode": {"label": "Away Mode", "description": "Switch off all controllable devices.",
                  "devices": {d[0]: False for d in SEED_DEVICES}},
    "relax_mode": {"label": "Relax Mode", "description": "Soft bedroom lighting and gentle airflow.",
                   "devices": {"bedroom_light": True, "hall_light": False, "fan": True}},
}
DEFAULT_RULES = [
    ("Motion turns on hall light", "motion", "hall_light", "on", 1, None),
    ("Evening lights", "time", "bedroom_light", "on", 0, "19:00"),
]

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

COMMAND_AUDIT = None
TELEMETRY = None

COMMAND_AUDIT = CommandAuditRepository(connect)
TELEMETRY = TelemetryRepository(connect)


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def request_data():
    """Return a JSON object; malformed or non-object bodies become an empty object."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS schema_migrations(
            version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS devices(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, room TEXT NOT NULL,
            watts REAL NOT NULL, is_on INTEGER NOT NULL DEFAULT 0,
            brightness INTEGER NOT NULL DEFAULT 100, speed INTEGER NOT NULL DEFAULT 1,
            protocol TEXT NOT NULL, temperature REAL DEFAULT 22.0, humidity REAL DEFAULT 45.0,
            updated_at TEXT NOT NULL, on_since TEXT
        );
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'system', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rules(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, trigger_type TEXT NOT NULL,
            device_id TEXT NOT NULL, action TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            schedule_time TEXT, created_at TEXT NOT NULL, threshold REAL DEFAULT 1.0,
            window_start TEXT, window_end TEXT, duration_seconds INTEGER DEFAULT 3600, last_fired_at TEXT,
            FOREIGN KEY(device_id) REFERENCES devices(id)
        );
        CREATE TABLE IF NOT EXISTS energy_samples(
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL,
            watts REAL NOT NULL, sampled_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS energy_ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL,
            day TEXT NOT NULL, kwh REAL NOT NULL DEFAULT 0,
            UNIQUE(device_id, day));
        CREATE TABLE IF NOT EXISTS energy_clock(
            device_id TEXT PRIMARY KEY, last_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS room_sensors(
            room TEXT PRIMARY KEY, temperature REAL NOT NULL, humidity REAL NOT NULL,
            updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL,
            category TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS undo_commands(
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL,
            previous_on INTEGER NOT NULL, created_at TEXT NOT NULL,
            command_group TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS command_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL,
            device_name TEXT NOT NULL, action TEXT NOT NULL, source TEXT NOT NULL,
            created_at TEXT NOT NULL, command_group TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS room_preferences(
            room TEXT PRIMARY KEY, target_temperature REAL NOT NULL DEFAULT 22.0,
            target_humidity REAL NOT NULL DEFAULT 45.0, notes TEXT NOT NULL DEFAULT '');
        """)
        device_columns = {r[1] for r in db.execute("PRAGMA table_info(devices)").fetchall()}
        if "on_since" not in device_columns:
            db.execute("ALTER TABLE devices ADD COLUMN on_since TEXT")
        rule_columns = {r[1] for r in db.execute("PRAGMA table_info(rules)").fetchall()}
        for column, declaration in (("threshold", "REAL DEFAULT 1.0"), ("window_start", "TEXT"),
                                    ("window_end", "TEXT"), ("duration_seconds", "INTEGER DEFAULT 3600"),
                                    ("last_fired_at", "TEXT")):
            if column not in rule_columns:
                db.execute(f"ALTER TABLE rules ADD COLUMN {column} {declaration}")
        undo_columns = {r[1] for r in db.execute("PRAGMA table_info(undo_commands)").fetchall()}
        if "command_group" not in undo_columns:
            db.execute("ALTER TABLE undo_commands ADD COLUMN command_group TEXT NOT NULL DEFAULT ''")
        count = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        if count == 0:
            for row in SEED_DEVICES:
                db.execute("""INSERT INTO devices
                    (id,name,kind,room,watts,brightness,speed,protocol,temperature,humidity,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (*row[:5], row[5], row[6], row[7], 22.0, 45.0, now_iso()))
            for rule in DEFAULT_RULES:
                db.execute("""INSERT INTO rules(name,trigger_type,device_id,action,enabled,schedule_time,created_at)
                              VALUES(?,?,?,?,?,?,?)""", (*rule, now_iso()))
            db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('home_name','My Smart Home')")
            db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('temperature_offset','0')")
            db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('humidity_offset','0')")
            db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('operating_mode','automatic')")
            db.execute("INSERT INTO events(message,category,created_at) VALUES(?,?,?)",
                       ("Smart Home system initialized", "system", now_iso()))
        db.execute("INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(1,?)", (now_iso(),))
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('operating_mode','automatic')")
        db.execute("UPDATE devices SET on_since=? WHERE is_on=1 AND on_since IS NULL", (now_iso(),))
        if db.execute("SELECT COUNT(*) FROM notifications").fetchone()[0] == 0:
            db.execute("INSERT INTO notifications(message,category,created_at) VALUES(?,?,?)", ("Smart Home system is ready", "system", now_iso()))
        rooms = db.execute("SELECT DISTINCT room FROM devices").fetchall()
        for room in rooms:
            db.execute("INSERT OR IGNORE INTO room_sensors(room,temperature,humidity,updated_at) VALUES(?,?,?,?)",
                       (room['room'], round(random.uniform(20.5,25.0),1), round(random.uniform(38,58),1), now_iso()))
            db.execute("INSERT OR IGNORE INTO room_preferences(room) VALUES(?)", (room['room'],))
        # Restore the original pattern-backed devices to their persisted on/off states.
        rows = db.execute("SELECT id,is_on FROM devices").fetchall()
    for row in rows:
        if row["id"] in HOME_FACADE.get_home_status():
            is_on = HOME_FACADE.get_home_status()[row["id"]].endswith("ON")
            if bool(row["is_on"]) != is_on:
                (HOME_FACADE.turn_on_device if row["is_on"] else HOME_FACADE.turn_off_device)(row["id"])

def save_state_snapshot():
    """Persist the current configuration/rule state as a portable JSON memento."""
    with STATE_LOCK:
        with connect() as db:
            settings = {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM settings")}
            devices = [dict(row) for row in db.execute(
                "SELECT id,name,kind,room,watts,is_on,brightness,speed,protocol FROM devices ORDER BY id")]
            rules = [dict(row) for row in db.execute(
                "SELECT id,name,trigger_type,device_id,action,enabled,schedule_time,threshold,window_start,window_end,duration_seconds FROM rules ORDER BY id")]
        snapshot = {"schema_version": 1, "exported_at": now_iso(), "settings": settings,
                    "devices": devices, "automation_rules": rules}
        STATE_STORE.save(snapshot)
        return snapshot


def log_event(message, category="system"):
    with connect() as db:
        stamp = now_iso()
        db.execute("INSERT INTO events(message,category,created_at) VALUES(?,?,?)", (message, category, stamp))
        db.execute("INSERT INTO notifications(message,category,created_at) VALUES(?,?,?)", (message, category, stamp))
    try:
        save_state_snapshot()
    except OSError:
        # The live SQLite database remains authoritative if the optional JSON backup is unavailable.
        pass

def device_row(device_id):
    with connect() as db:
        row = db.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
        return dict(row) if row else None

def set_device_power(device_id, turn_on, source="dashboard", record_undo=True, command_group=None):
    with STATE_LOCK:
        row = device_row(device_id)
        if not row:
            raise ValueError("Device not found")
        # Use the existing Facade/Command/Adapter/Bridge/Factory-backed device
        # for the four original devices. Extra simulated devices are persisted here.
        if device_id in HOME_FACADE.get_home_status():
            (HOME_FACADE.turn_on_device if turn_on else HOME_FACADE.turn_off_device)(device_id)
        with connect() as db:
            stamp = now_iso()
            db.execute("UPDATE devices SET is_on=?,updated_at=?,on_since=? WHERE id=?",
                       (1 if turn_on else 0, stamp, stamp if turn_on else None, device_id))
        if record_undo:
            with connect() as db:
                db.execute("INSERT INTO undo_commands(device_id,previous_on,created_at,command_group) VALUES(?,?,?,?)",
                           (device_id, int(bool(row['is_on'])), now_iso(), command_group or uuid.uuid4().hex))
                db.execute("DELETE FROM undo_commands WHERE id NOT IN (SELECT id FROM undo_commands ORDER BY id DESC LIMIT 60)")
        action = "ON" if turn_on else "OFF"
        stamp = now_iso()
        COMMAND_AUDIT.add(device_id=device_id, device_name=row["name"], action=action,
                          source=source, created_at=stamp, command_group=command_group or "")
        log_event(f"{row['name']} turned {action} ({source})", "device")
        return device_row(device_id)

def update_device_setting(device_id, field, value):
    row = device_row(device_id)
    if not row:
        raise ValueError("Device not found")
    if field == "brightness":
        if row["kind"] != "light" or not 0 <= int(value) <= 100:
            raise ValueError("Brightness must be 0–100 and applies to lights")
        value = int(value)
    elif field == "speed":
        if row["kind"] != "fan" or not 1 <= int(value) <= 5:
            raise ValueError("Fan speed must be between 1 and 5")
        value = int(value)
    else:
        raise ValueError("Unsupported setting")
    with connect() as db:
        db.execute(f"UPDATE devices SET {field}=?,updated_at=? WHERE id=?", (value, now_iso(), device_id))
    log_event(f"{row['name']} {field} set to {value}", "device")
    return device_row(device_id)

def run_scene(scene_id):
    scene = SCENES.get(scene_id)
    if not scene:
        raise ValueError("Unknown scene")
    command_group = uuid.uuid4().hex
    for device_id, turn_on in scene["devices"].items():
        if device_row(device_id):
            set_device_power(device_id, turn_on, source=f"scene: {scene['label']}", command_group=command_group)
    log_event(f"Scene activated: {scene['label']}", "scene")

def process_motion():
    if operating_mode() == "automatic":
        MOTION_SENSOR.detect_motion()  # Observer notifies the rule engine and notifier in automatic mode.
    log_event("Motion detected in Hallway", "sensor")
    evaluate_rules("motion")

def process_trigger(trigger_type):
    if trigger_type == "motion":
        process_motion()
        return
    if operating_mode() != "automatic":
        log_event(f"{trigger_type.replace('_',' ').title()} event received (manual mode; automation paused)", "sensor")
        return
    evaluate_rules(trigger_type)
    log_event(f"Automation trigger received: {trigger_type}", "sensor")

def operating_mode():
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key='operating_mode'").fetchone()
    return row['value'] if row else 'automatic'

def evaluate_rules(trigger_type, context=None):
    if operating_mode() != 'automatic':
        return 0
    context = context or {}
    with connect() as db:
        rules = db.execute("SELECT * FROM rules WHERE enabled=1 AND trigger_type=?", (trigger_type,)).fetchall()
    fired = 0
    for rule in rules:
        condition_met = False
        if trigger_type == "time":
            condition_met = rule["schedule_time"] == datetime.now().strftime("%H:%M")
        elif trigger_type == "energy_threshold":
            condition_met = EnergyThresholdCondition(float(rule["threshold"] or 1.0)).evaluate(context)
        elif trigger_type == "time_window":
            condition_met = TimeWindowCondition(rule["window_start"] or "23:00", rule["window_end"] or "06:00").evaluate(context)
        elif trigger_type == "anomaly":
            condition_met = AnomalyCondition(int(rule["duration_seconds"] or 3600)).evaluate(context)
        else:
            condition_met = True
        if not condition_met:
            continue
        if trigger_type == "anomaly" and context.get("device_id") and context["device_id"] != rule["device_id"]:
            continue
        # Avoid repeatedly firing the same data-driven condition every worker tick.
        last_fired = rule["last_fired_at"]
        if trigger_type in {"energy_threshold", "time_window", "anomaly"} and last_fired:
            try:
                fired_at = datetime.fromisoformat(last_fired)
                if trigger_type == "energy_threshold" and fired_at.date() == datetime.now().astimezone().date():
                    continue
                cooldown = 300 if trigger_type == "time_window" else 3600
                if trigger_type != "energy_threshold" and (datetime.now().astimezone() - fired_at).total_seconds() < cooldown:
                    continue
            except ValueError:
                pass
        current = device_row(rule["device_id"])
        if not current:
            continue
        turn_on = (not bool(current["is_on"])) if rule["action"] == "toggle" else rule["action"] == "on"
        set_device_power(rule["device_id"], turn_on, source=f"automation: {rule['name']}")
        with connect() as db:
            db.execute("UPDATE rules SET last_fired_at=? WHERE id=?", (now_iso(), rule["id"]))
        log_event(f"Automation executed: {rule['name']}", "automation")
        fired += 1
    return fired

def scheduler_loop():
    last_minute = None
    while True:
        minute = datetime.now().strftime("%Y-%m-%d %H:%M")
        if minute != last_minute:
            evaluate_rules("time")
            last_minute = minute
        time.sleep(15)

def simulation_worker_loop():
    """Periodic worker for simulated telemetry and data-driven automation."""
    while True:
        try:
            sensor_data()
            energy = energy_data()
            evaluate_rules("energy_threshold", {"daily_kwh": energy["today_kwh"]})
            evaluate_rules("time_window", {"now": datetime.now().time()})
            with connect() as db:
                active = db.execute("SELECT id,name,on_since FROM devices WHERE is_on=1 AND on_since IS NOT NULL").fetchall()
            now = datetime.now().astimezone()
            for device in active:
                try:
                    seconds = max(0, (now - datetime.fromisoformat(device["on_since"])).total_seconds())
                except (TypeError, ValueError):
                    seconds = 0
                evaluate_rules("anomaly", {"device_id": device["id"], "device_name": device["name"], "on_seconds": seconds})
        except Exception as exc:
            # Keep a transient simulation failure from killing the worker thread.
            log_event(f"Simulation worker recovered from: {type(exc).__name__}", "system")
        time.sleep(10)


def energy_data(days=7):
    """Accumulate estimated device energy using elapsed wall-clock time."""
    days = max(7, min(30, int(days)))
    stamp = datetime.now().astimezone()
    day = stamp.date().isoformat()
    with STATE_LOCK, connect() as db:
        devices = db.execute("SELECT id,name,watts,is_on FROM devices ORDER BY name").fetchall()
        for d in devices:
            previous = db.execute("SELECT last_at FROM energy_clock WHERE device_id=?", (d['id'],)).fetchone()
            if previous:
                try:
                    elapsed = max(0.0, min(86400.0, (stamp - datetime.fromisoformat(previous['last_at'])).total_seconds()))
                except ValueError:
                    elapsed = 0.0
                kwh = (float(d['watts']) / 1000.0) * (elapsed / 3600.0) if d['is_on'] else 0.0
                if kwh:
                    db.execute("INSERT INTO energy_ledger(device_id,day,kwh) VALUES(?,?,?) ON CONFLICT(device_id,day) DO UPDATE SET kwh=kwh+excluded.kwh", (d['id'], day, kwh))
            db.execute("INSERT INTO energy_clock(device_id,last_at) VALUES(?,?) ON CONFLICT(device_id) DO UPDATE SET last_at=excluded.last_at", (d['id'], stamp.isoformat()))
        active_watts = sum(float(r['watts']) for r in devices if r['is_on'])
        daily = db.execute("SELECT COALESCE(SUM(kwh),0) FROM energy_ledger WHERE day=?", (day,)).fetchone()[0]
        yesterday_day = (stamp.date() - timedelta(days=1)).isoformat()
        yesterday = db.execute("SELECT COALESCE(SUM(kwh),0) FROM energy_ledger WHERE day=?", (yesterday_day,)).fetchone()[0]
        breakdown = db.execute("SELECT d.id,d.name,d.watts,d.is_on,COALESCE(e.kwh,0) AS daily_kwh FROM devices d LEFT JOIN energy_ledger e ON e.device_id=d.id AND e.day=? ORDER BY d.name", (day,)).fetchall()
        history = db.execute("SELECT day,SUM(kwh) AS kwh FROM energy_ledger WHERE day>=date(?, ?) GROUP BY day ORDER BY day", (day, f"-{days-1} day")).fetchall()
        device_history = db.execute("SELECT d.name,COALESCE(SUM(e.kwh),0) AS kwh FROM devices d LEFT JOIN energy_ledger e ON e.device_id=d.id AND e.day>=date(?, ?) GROUP BY d.id ORDER BY kwh DESC", (day, f"-{days-1} day")).fetchall()
        samples = db.execute("SELECT sampled_at,watts FROM energy_samples WHERE device_id='__home__' ORDER BY id DESC LIMIT 24").fetchall()
    should_sample = True
    if samples:
        try:
            should_sample = (stamp - datetime.fromisoformat(samples[0]["sampled_at"])).total_seconds() >= 10
        except (TypeError, ValueError):
            should_sample = True
    if should_sample:
        TELEMETRY.record_power_sample("__home__", active_watts, stamp.isoformat())
    samples = list(reversed(samples))
    if should_sample:
        samples.append({'sampled_at':stamp.isoformat(),'watts':active_watts})
    return {"active_watts":round(active_watts,1), "estimated_kwh_per_hour":round(active_watts/1000,3),
            "today_kwh":round(float(daily),5),
            "yesterday_kwh":round(float(yesterday),5),
            "day_over_day_change_pct":round(((float(daily)-float(yesterday))/float(yesterday))*100,1) if float(yesterday)>0 else None,
            "recent_samples":[{"time":r['sampled_at'][11:16],"watts":r['watts']} for r in samples[-24:]],
            "device_breakdown":[{"id":r['id'],"name":r['name'],"watts":round(float(r['watts']) if r['is_on'] else 0,1),"daily_kwh":round(float(r['daily_kwh']),5)} for r in breakdown],
            "daily_history":[{"day":r['day'],"kwh":round(float(r['kwh']),5)} for r in history],
            "device_history":[{"name":r['name'],"kwh":round(float(r['kwh']),5)} for r in device_history],
            "estimated":True}

def sensor_data():
    with connect() as db:
        rows = db.execute("SELECT * FROM room_sensors ORDER BY room").fetchall()
        result=[]
        for row in rows:
            # Small bounded drift makes the room readings visibly simulated, not static.
            temp=max(18.0,min(30.0,float(row['temperature'])+random.uniform(-0.15,0.15)))
            humidity=max(25.0,min(70.0,float(row['humidity'])+random.uniform(-0.7,0.7)))
            db.execute("UPDATE room_sensors SET temperature=?,humidity=?,updated_at=? WHERE room=?",(round(temp,1),round(humidity,1),now_iso(),row['room']))
            result.append({"room":row['room'],"temperature":round(temp,1),"humidity":round(humidity,1)})
    return result

def dashboard_state():
    with connect() as db:
        devices = [dict(r) for r in db.execute("SELECT * FROM devices ORDER BY room,name")]
        events = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 30")]
        rules = [dict(r) for r in db.execute("SELECT * FROM rules ORDER BY id DESC")]
        home_name = db.execute("SELECT value FROM settings WHERE key='home_name'").fetchone()
        unread = db.execute("SELECT COUNT(*) FROM notifications WHERE is_read=0").fetchone()[0]
        notifications = [dict(r) for r in db.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 20")]
        mode_row = db.execute("SELECT value FROM settings WHERE key='operating_mode'").fetchone()
    for device in devices:
        device["architecture_badges"] = []
        if device["protocol"].lower() in ("wifi", "mqtt"):
            device["architecture_badges"].append("Wi-Fi" if device["protocol"].lower() == "wifi" else "MQTT")
            device["architecture_badges"].append("Bridge")
        if "legacy" in device["protocol"].lower():
            device["architecture_badges"].append("Legacy Adapter")
        if device["id"] == "fan":
            device["architecture_badges"].append("Energy Decorator")
    active = sum(d["is_on"] for d in devices)
    with connect() as db:
        room_preferences = [dict(r) for r in db.execute("SELECT * FROM room_preferences ORDER BY room").fetchall()]
    with connect() as db:
        undo_row = db.execute("SELECT id,device_id FROM undo_commands ORDER BY id DESC LIMIT 1").fetchone()
    command_history = COMMAND_AUDIT.list_recent(25)
    return {"home_name": home_name["value"] if home_name else "My Smart Home",
            "devices": devices, "events": events, "rules": rules, "room_preferences": room_preferences,
            "can_undo": bool(undo_row),
            "scenes": SCENES, "energy": energy_data(), "sensors": sensor_data(),
            "mode": mode_row["value"] if mode_row else "automatic", "notifications": notifications, "unread_notifications": unread,
            "command_history": command_history,
            "summary": {"total":len(devices),"active":active,"inactive":len(devices)-active,
                        "rooms":len(set(d["room"] for d in devices)),
                        "automations":sum(r["enabled"] for r in rules)}}

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error":"Authentication required"}), 401
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","")
        password = request.form.get("password","")
        expected_user = os.environ.get("SMART_HOME_USER", "admin")
        expected_password = os.environ.get("SMART_HOME_PASSWORD", "home1234")
        if username == expected_user and password == expected_password:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("index"))
        flash("Incorrect username or password", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template("dashboard.html")

@app.route("/settings")
@login_required
def settings_page():
    """Dedicated settings view while retaining the in-dashboard settings section."""
    return render_template("settings_page.html")


@app.route("/api/state")
@login_required
def api_state():
    return jsonify(dashboard_state())

@app.route("/api/device/<device_id>/power", methods=["POST"])
@login_required
def api_device_power(device_id):
    data = request_data()
    try:
        if not isinstance(data.get("on"), bool):
            return jsonify({"error":"The on field must be a boolean."}),400
        row = set_device_power(device_id, data["on"], "dashboard")
        return jsonify({"device":row,"state":dashboard_state()})
    except ValueError as exc:
        return jsonify({"error":str(exc)}), 400

@app.route("/api/device/<device_id>/setting", methods=["POST"])
@login_required
def api_device_setting(device_id):
    data = request_data()
    try:
        row = update_device_setting(device_id, data.get("field"), data.get("value"))
        return jsonify({"device":row})
    except (ValueError, TypeError, OverflowError) as exc:
        return jsonify({"error":str(exc)}), 400

@app.route("/api/motion", methods=["POST"])
@login_required
def api_motion():
    process_motion()
    return jsonify({"ok":True,"state":dashboard_state()})

@app.route("/api/all-off", methods=["POST"])
@login_required
def api_all_off():
    command_group = uuid.uuid4().hex
    for d in dashboard_state()["devices"]:
        if d["is_on"]:
            set_device_power(d["id"], False, "all-off", command_group=command_group)
    log_event("All devices switched off", "system")
    return jsonify(dashboard_state())

@app.route("/api/undo", methods=["POST"])
@login_required
def api_undo():
    with STATE_LOCK, connect() as db:
        latest = db.execute("SELECT command_group FROM undo_commands ORDER BY id DESC LIMIT 1").fetchone()
        if not latest:
            return jsonify({"error":"There is no command to undo."}), 409
        group = latest["command_group"]
        if not group:  # compatibility with undo rows created by an older build
            command = db.execute("SELECT * FROM undo_commands ORDER BY id DESC LIMIT 1").fetchone()
            commands = [command]
            db.execute("DELETE FROM undo_commands WHERE id=?", (command["id"],))
        else:
            commands = db.execute("SELECT * FROM undo_commands WHERE command_group=? ORDER BY id DESC", (group,)).fetchall()
            db.execute("DELETE FROM undo_commands WHERE command_group=?", (group,))
    for command in commands:
        row = device_row(command["device_id"])
        if row:
            set_device_power(row["id"], bool(command["previous_on"]), source="undo", record_undo=False)
            log_event(f"Undid last command for {row['name']}", "command")
    return jsonify(dashboard_state())

@app.route("/api/scene/<scene_id>", methods=["POST"])
@login_required
def api_scene(scene_id):
    try:
        run_scene(scene_id)
        return jsonify(dashboard_state())
    except ValueError as exc:
        return jsonify({"error":str(exc)}), 400

@app.route("/api/rules", methods=["POST"])
@login_required
def api_create_rule():
    data = request_data()
    raw_name = data.get("name")
    name = raw_name.strip() if isinstance(raw_name, str) else ""
    trigger = data.get("trigger_type")
    device_id = data.get("device_id")
    action = data.get("action")
    schedule_time = data.get("schedule_time") or None
    if not isinstance(name, str) or not name.strip() or len(name)>70 or trigger not in ("motion","time","door_open","temperature_high","humidity_high","energy_threshold","time_window","anomaly") or action not in ("on","off","toggle") or not isinstance(device_id,str) or not device_row(device_id):
        return jsonify({"error":"Enter a rule name and valid trigger, device and action."}), 400
    if trigger == "time":
        try:
            if not isinstance(schedule_time, str):
                raise ValueError
            datetime.strptime(schedule_time, "%H:%M")
        except (ValueError, TypeError):
            return jsonify({"error":"Scheduled rules require a valid HH:MM time."}), 400
    if trigger != "time":
        schedule_time = None
    raw_threshold = data.get("threshold", 1.0)
    raw_duration = data.get("duration_seconds", 3600)
    try:
        if isinstance(raw_threshold, bool) or isinstance(raw_duration, bool):
            raise ValueError
        threshold = float(raw_threshold)
        duration_seconds = int(raw_duration)
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error":"Threshold and duration must be numeric values."}), 400
    window_start, window_end = data.get("window_start", "23:00"), data.get("window_end", "06:00")
    if trigger == "energy_threshold" and not 0.01 <= threshold <= 10000:
        return jsonify({"error":"Energy threshold must be between 0.01 and 10000 kWh."}), 400
    if trigger == "anomaly" and not 60 <= duration_seconds <= 604800:
        return jsonify({"error":"Anomaly duration must be between 60 and 604800 seconds."}), 400
    if trigger == "time_window":
        try:
            datetime.strptime(window_start, "%H:%M"); datetime.strptime(window_end, "%H:%M")
        except (ValueError, TypeError):
            return jsonify({"error":"Time window requires valid HH:MM start and end values."}), 400
    with connect() as db:
        db.execute("""INSERT INTO rules(name,trigger_type,device_id,action,enabled,schedule_time,created_at,threshold,window_start,window_end,duration_seconds)
                      VALUES(?,?,?,?,1,?,?,?,?,?,?)""", (name,trigger,device_id,action,schedule_time,now_iso(),float(threshold),window_start,window_end,int(duration_seconds)))
    log_event(f"Automation rule created: {name}", "automation")
    return jsonify(dashboard_state()), 201

@app.route("/api/rules/preset/<preset>", methods=["POST"])
@login_required
def api_rule_preset(preset):
    presets = {
        "night_mode": ("Night Mode · switch fan off", "time_window", "fan", "off", None, "23:00", "06:00"),
        "motion_security": ("Motion Security · hall light on", "motion", "hall_light", "on", None, None, None),
    }
    if preset not in presets:
        return jsonify({"error":"Unknown automation preset."}), 404
    name, trigger, device_id, action, schedule, window_start, window_end = presets[preset]
    # Use the existing Director/Builder recipes as the pattern-level preset source.
    try:
        director = RuleDirector(AutomationRuleBuilder())
        if preset == "motion_security":
            director.build_motion_rule(HOME_FACADE._devices.get_device("hall_light"))
        else:
            director.build_night_rule(HOME_FACADE._devices.get_device("fan"))
    except Exception:
        pass
    with connect() as db:
        db.execute("INSERT INTO rules(name,trigger_type,device_id,action,enabled,schedule_time,created_at,window_start,window_end) VALUES(?,?,?,?,1,?,?,?,?)",
                   (name, trigger, device_id, action, schedule, now_iso(), window_start, window_end))
    log_event(f"Automation preset added: {name}", "automation")
    return jsonify(dashboard_state()), 201


@app.route("/api/rules/<int:rule_id>", methods=["PATCH","DELETE"])
@login_required
def api_rule(rule_id):
    if request.method == "DELETE":
        with connect() as db:
            cur=db.execute("DELETE FROM rules WHERE id=?", (rule_id,))
            if cur.rowcount==0: return jsonify({"error":"Rule not found"}),404
        log_event(f"Automation rule {rule_id} deleted", "automation")
    else:
        data = request_data()
        if not isinstance(data.get("enabled"),bool): return jsonify({"error":"enabled must be a boolean"}),400
        with connect() as db:
            cur=db.execute("UPDATE rules SET enabled=? WHERE id=?", (1 if data["enabled"] else 0, rule_id))
            if cur.rowcount==0: return jsonify({"error":"Rule not found"}),404
        log_event(f"Automation rule {rule_id} updated", "automation")
    return jsonify(dashboard_state())

@app.route("/api/settings", methods=["POST"])
@login_required
def api_settings():
    data = request_data()
    raw_home_name = data.get("home_name")
    if not isinstance(raw_home_name, str):
        return jsonify({"error":"Home name must be text."}), 400
    home_name = raw_home_name.strip()
    if not home_name or len(home_name) > 60:
        return jsonify({"error":"Home name cannot be empty"}), 400
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('home_name',?)", (home_name,))
    HomeConfig.get_instance().set("home_name", home_name)
    log_event(f"Home name changed to {home_name}", "settings")
    return jsonify({"home_name":home_name})

@app.route("/api/rooms/power", methods=["POST"])
@login_required
def api_room_power():
    data = request_data()
    room, turn_on = data.get("room"), data.get("on")
    if not isinstance(room, str) or not room.strip() or not isinstance(turn_on, bool):
        return jsonify({"error":"room must be a non-empty string and on must be boolean."}), 400
    with connect() as db:
        rows = db.execute("SELECT id FROM devices WHERE room=?", (room.strip(),)).fetchall()
    if not rows:
        return jsonify({"error":"Room not found or contains no devices."}), 404
    command_group = uuid.uuid4().hex
    for item in rows:
        set_device_power(item["id"], turn_on, source=f"room control: {room}", command_group=command_group)
    log_event(f"All devices in {room} switched {'ON' if turn_on else 'OFF'}", "room")
    return jsonify(dashboard_state())

@app.route("/api/device/<device_id>/config", methods=["PATCH"])
@login_required
def api_device_config(device_id):
    data = request_data()
    row = device_row(device_id)
    if not row:
        return jsonify({"error":"Device not found."}), 404
    name = data.get("name", row["name"])
    room = data.get("room", row["room"])
    watts = data.get("watts", row["watts"])
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 60:
        return jsonify({"error":"Device name must contain 1–60 characters."}), 400
    if not isinstance(room, str) or not room.strip() or len(room.strip()) > 40:
        return jsonify({"error":"Room name must contain 1–40 characters."}), 400
    if isinstance(watts, bool) or not isinstance(watts, (int, float)) or not 0 <= watts <= 5000:
        return jsonify({"error":"Device wattage must be between 0 and 5000."}), 400
    old_room = row["room"]
    with connect() as db:
        db.execute("UPDATE devices SET name=?,room=?,watts=?,updated_at=? WHERE id=?",
                   (name.strip(), room.strip(), float(watts), now_iso(), device_id))
        db.execute("INSERT OR IGNORE INTO room_sensors(room,temperature,humidity,updated_at) VALUES(?,?,?,?)",
                   (room.strip(), 22.0, 45.0, now_iso()))
        db.execute("INSERT OR IGNORE INTO room_preferences(room) VALUES(?)", (room.strip(),))
        if old_room != room.strip() and not db.execute("SELECT 1 FROM devices WHERE room=?", (old_room,)).fetchone():
            db.execute("DELETE FROM room_sensors WHERE room=?", (old_room,))
            db.execute("DELETE FROM room_preferences WHERE room=?", (old_room,))
    log_event(f"Device configuration updated: {name.strip()}", "settings")
    return jsonify({"device":device_row(device_id), "state":dashboard_state()})

@app.route("/api/rooms/config", methods=["PATCH"])
@login_required
def api_room_config():
    data = request_data()
    room = data.get("room")
    new_name = data.get("name", room)
    target_temp = data.get("target_temperature", 22.0)
    target_humidity = data.get("target_humidity", 45.0)
    notes = data.get("notes", "")
    if not isinstance(room, str) or not room.strip():
        return jsonify({"error":"A room name is required."}), 400
    if not isinstance(new_name, str) or not new_name.strip() or len(new_name.strip()) > 40:
        return jsonify({"error":"Room name must contain 1–40 characters."}), 400
    if isinstance(target_temp, bool) or not isinstance(target_temp, (int,float)) or not 10 <= target_temp <= 35:
        return jsonify({"error":"Target temperature must be between 10 and 35°C."}), 400
    if isinstance(target_humidity, bool) or not isinstance(target_humidity, (int,float)) or not 20 <= target_humidity <= 80:
        return jsonify({"error":"Target humidity must be between 20 and 80%."}), 400
    if not isinstance(notes, str) or len(notes) > 200:
        return jsonify({"error":"Room notes must be 200 characters or fewer."}), 400
    with connect() as db:
        exists = db.execute("SELECT 1 FROM devices WHERE room=?", (room,)).fetchone()
        if not exists:
            return jsonify({"error":"Room not found."}), 404
        collision = db.execute("SELECT 1 FROM devices WHERE room=? AND room<>?", (new_name.strip(), room)).fetchone()
        if collision:
            return jsonify({"error":"A room with that name already exists."}), 409
        db.execute("UPDATE devices SET room=? WHERE room=?", (new_name.strip(), room))
        sensor = db.execute("SELECT * FROM room_sensors WHERE room=?", (room,)).fetchone()
        if sensor:
            db.execute("UPDATE room_sensors SET room=? WHERE room=?", (new_name.strip(), room))
        db.execute("DELETE FROM room_preferences WHERE room=?", (room,))
        db.execute("INSERT INTO room_preferences(room,target_temperature,target_humidity,notes) VALUES(?,?,?,?)",
                   (new_name.strip(), float(target_temp), float(target_humidity), notes.strip()))
    log_event(f"Room settings updated: {new_name.strip()}", "settings")
    return jsonify(dashboard_state())

@app.route("/api/trigger", methods=["POST"])
@login_required
def api_trigger():
    data = request_data()
    trigger = data.get("trigger_type")
    allowed = {"motion", "door_open", "temperature_high", "humidity_high", "energy_threshold", "time_window", "anomaly"}
    if not isinstance(trigger, str) or trigger not in allowed:
        return jsonify({"error":f"trigger_type must be one of {', '.join(sorted(allowed))}."}), 400
    if trigger in {"energy_threshold", "time_window", "anomaly"}:
        if trigger == "energy_threshold":
            energy = energy_data(); evaluate_rules(trigger, {"daily_kwh": max(energy["today_kwh"], 1.0)})
        elif trigger == "time_window":
            evaluate_rules(trigger, {"now": datetime.now().time()})
        else:
            evaluate_rules(trigger, {"on_seconds": 86400})
        log_event(f"{trigger.replace('_',' ').title()} test event", "sensor")
    else:
        process_trigger(trigger)
    return jsonify(dashboard_state())

@app.route("/api/commands")
@login_required
def api_commands():
    return jsonify({"commands": COMMAND_AUDIT.list_recent(100)})

@app.route("/api/commands/export")
@login_required
def api_commands_export():
    fmt = request.args.get("format", "json").lower()
    rows = COMMAND_AUDIT.list_recent(500)
    if fmt == "csv":
        output = io.StringIO()
        fields = ["id", "device_id", "device_name", "action", "source", "created_at", "command_group"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment; filename=command-audit.csv"})
    if fmt != "json":
        return jsonify({"error":"format must be csv or json"}), 400
    return Response(json.dumps({"commands": rows}, indent=2), mimetype="application/json",
                    headers={"Content-Disposition":"attachment; filename=command-audit.json"})

@app.route("/api/state/snapshot")
@login_required
def api_state_snapshot():
    snapshot = save_state_snapshot()
    return Response(json.dumps(snapshot, indent=2), mimetype="application/json",
                    headers={"Content-Disposition":"attachment; filename=smart-home-state.json"})

@app.route("/api/export")
@login_required
def api_export():
    return jsonify(dashboard_state())


@app.route("/api/mode", methods=["POST"])
@login_required
def api_mode():
    data=request_data()
    mode=data.get("mode")
    if mode not in ("manual","automatic"):
        return jsonify({"error":"Mode must be manual or automatic."}),400
    with connect() as db:
        db.execute("INSERT INTO settings(key,value) VALUES('operating_mode',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(mode,))
    log_event(f"Operating mode changed to {mode}","settings")
    return jsonify({"mode":mode})

@app.route("/api/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def api_notification_read(notification_id):
    with connect() as db:
        cur=db.execute("UPDATE notifications SET is_read=1 WHERE id=?",(notification_id,))
        if cur.rowcount==0: return jsonify({"error":"Notification not found"}),404
    return jsonify({"ok":True})

@app.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_notifications_read_all():
    with connect() as db: db.execute("UPDATE notifications SET is_read=1")
    return jsonify({"ok":True})

@app.route("/api/energy")
@login_required
def api_energy():
    try:
        days = int(request.args.get("days", "7"))
    except ValueError:
        return jsonify({"error":"days must be 7 or 30"}), 400
    if days not in (7, 30):
        return jsonify({"error":"days must be 7 or 30"}), 400
    return jsonify(energy_data(days))

@app.route("/api/sensors")
@login_required
def api_sensors():
    return jsonify(sensor_data())

@app.route("/health")
def health():
    return jsonify({"status":"ok","application":"Smart Home Automation"})

init_db()
with connect() as _db:
    _home_name_row = _db.execute("SELECT value FROM settings WHERE key='home_name'").fetchone()
if _home_name_row:
    HomeConfig.get_instance().set("home_name", _home_name_row["value"])
save_state_snapshot()

if os.environ.get("SMART_HOME_DISABLE_SCHEDULER") != "1":
    threading.Thread(target=scheduler_loop, daemon=True, name="smart-home-scheduler").start()
    threading.Thread(target=simulation_worker_loop, daemon=True, name="smart-home-simulation-worker").start()

if __name__ == "__main__":
    print("Smart Home dashboard: http://127.0.0.1:5000")
    print("Development login: admin / home1234 (change before sharing)")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
