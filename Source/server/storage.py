"""
server/storage.py — In-memory storage layer.

Stores sensor registrations and readings in plain Python dicts/lists.
Thread-safe enough for single-threaded asyncio use.

Design decision: in-memory (not SQLite) for simplicity and speed.
All data is lost on restart — acceptable for a prototype.
"""
from __future__ import annotations

from typing import Iterable, Optional
import time


class Storage:
    """In-memory storage for sensors and readings."""

    def __init__(self) -> None:
        # { sensor_id: dict }
        self._sensors: dict[str, dict] = {}
        # { sensor_id: [dict, ...] } — sorted by timestamp
        self._readings: dict[str, list[dict]] = {}

    async def add_sensor(self, sensor: dict) -> None:
        sid = sensor["sensor_id"]
        self._sensors[sid] = sensor
        if sid not in self._readings:
            self._readings[sid] = []

    async def remove_sensor(self, sensor_id: str) -> None:
        self._sensors.pop(sensor_id, None)
        self._readings.pop(sensor_id, None)
    async def list_sensors(self) -> list[dict]:
        return list(self._sensors.values())

    async def get_sensor(self, sensor_id: str) -> Optional[dict]:
        return self._sensors.get(sensor_id)

    async def add_reading(self, reading: dict) -> None:
        sid = reading["sensor_id"]
        if sid not in self._readings:
            self._readings[sid] = []
        self._readings[sid].append(reading)

    async def get_readings(
        self,
        sensor_id: str,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
    ) -> list[dict]:
        rows = self._readings.get(sensor_id, [])
        if from_ts is not None:
            rows = [r for r in rows if r["timestamp"] >= from_ts]
        if to_ts is not None:
            rows = [r for r in rows if r["timestamp"] <= to_ts]
        return rows
