"""
client/simulator.py — Single-sensor simulation logic.

Each simulated sensor:
  - Connects to the telemetry server over TCP.
  - Generates plausible readings on its configured interval using a
    random-walk approach (small increments bounded by a configured range).
  - Encodes each reading as a Protobuf message and writes a 4-byte
    big-endian length-prefixed frame on the socket.
  - Reconnects with exponential backoff after transient network failures.
"""
from __future__ import annotations

import asyncio
import logging
import random
import struct
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import telemetry_pb2

log = logging.getLogger(__name__)
_UNITS = {
    "temperature":   "°C",
    "humidity":      "%",
    "soil_moisture": "%",
    "light":         "lux",
}

_DEFAULT_RANGES = {
    "temperature":   (15.0, 40.0),
    "humidity":      (30.0, 95.0),
    "soil_moisture": (10.0, 80.0),
    "light":         (0.0, 100_000.0),
}

_BACKOFF_INITIAL = 1.0   
_BACKOFF_MAX     = 60.0


class SensorSimulator:
    """Simulates one sensor pushing readings to the telemetry server."""

    def __init__(
        self,
        sensor_id: str,
        sensor_type: str,
        interval_seconds: float,
        host: str,
        port: int,
        value_range: tuple[float, float] | None = None,
    ) -> None:
        self.sensor_id        = sensor_id
        self.sensor_type      = sensor_type
        self.interval_seconds = interval_seconds
        self.host             = host
        self.port             = port
        self.unit             = _UNITS.get(sensor_type, "")

        lo, hi = value_range or _DEFAULT_RANGES.get(sensor_type, (0.0, 100.0))
        self._range_lo = lo
        self._range_hi = hi
        self._current_value = (lo + hi) / 2.0
        self._step = (hi - lo) * 0.01

    async def run(self) -> None:
        """Connect, then push readings on the configured interval forever."""
        backoff = _BACKOFF_INITIAL
        while True:
            try:
                log.info("[%s] Connecting to %s:%d …", self.sensor_id, self.host, self.port)
                reader, writer = await asyncio.open_connection(self.host, self.port)
                log.info("[%s] Connected.", self.sensor_id)
                backoff = _BACKOFF_INITIAL   # reset on success
                await self._push_loop(writer)
            except (ConnectionRefusedError, OSError) as exc:
                log.warning("[%s] Connection failed: %s. Retrying in %.1fs …",
                            self.sensor_id, exc, backoff)
            except Exception as exc:
                log.error("[%s] Unexpected error: %s. Retrying in %.1fs …",
                          self.sensor_id, exc, backoff)
            finally:
                pass

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

    async def _push_loop(self, writer: asyncio.StreamWriter) -> None:
        """Inner loop: generate → encode → frame → send → sleep."""
        try:
            while True:
                reading = self._generate_reading()
                payload = reading.SerializeToString()
                frame   = struct.pack(">I", len(payload)) + payload

                writer.write(frame)
                await writer.drain()

                log.debug("[%s] Sent %s=%.2f %s",
                          self.sensor_id, self.sensor_type,
                          reading.value, self.unit)

                await asyncio.sleep(self.interval_seconds)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def _generate_reading(self) -> telemetry_pb2.Reading:
        """Produce a plausible next Reading using a bounded random walk."""
        delta = random.uniform(-self._step * 5, self._step * 5)
        self._current_value += delta
        self._current_value = max(self._range_lo,
                                  min(self._range_hi, self._current_value))

        return telemetry_pb2.Reading(
            sensor_id = self.sensor_id,
            type      = self.sensor_type,
            value     = round(self._current_value, 2),
            timestamp = time.time(),
            unit      = self.unit,
        )
