"""Repository / DAO layer for durable telemetry and command audit records.

The repositories accept a connection factory so the application and tests can
choose their own SQLite database without leaking SQL into domain objects.
"""
from __future__ import annotations

import sqlite3
from typing import Callable, Iterable

ConnectionFactory = Callable[[], sqlite3.Connection]


class CommandAuditRepository:
    def __init__(self, connect: ConnectionFactory):
        self._connect = connect

    def add(self, *, device_id: str, device_name: str, action: str,
            source: str, created_at: str, command_group: str = "") -> int:
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO command_audit
                   (device_id, device_name, action, source, created_at, command_group)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (device_id, device_name, action, source, created_at, command_group),
            )
            return int(cursor.lastrowid)

    def list_recent(self, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM command_audit ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]


class TelemetryRepository:
    """DAO for timestamped power samples and daily per-device energy totals."""
    def __init__(self, connect: ConnectionFactory):
        self._connect = connect

    def record_power_sample(self, device_id: str, watts: float, sampled_at: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO energy_samples(device_id, watts, sampled_at) VALUES (?, ?, ?)",
                (device_id, float(watts), sampled_at),
            )

    def daily_totals(self, day: str) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT device_id, kwh FROM energy_ledger WHERE day=? ORDER BY device_id",
                (day,),
            ).fetchall()]
