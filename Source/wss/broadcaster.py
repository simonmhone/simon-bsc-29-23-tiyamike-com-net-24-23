"""
wss/broadcaster.py — Fan-out of readings to connected WebSocket clients.

Slow-consumer strategy: DROP.
If a client's send() takes longer than SEND_TIMEOUT seconds, we skip that
reading for that client.  This keeps fast consumers unaffected.
The client will simply miss readings during congestion — acceptable for a
live dashboard.
"""
from __future__ import annotations

import asyncio
import json
import logging

log = logging.getLogger(__name__)

SEND_TIMEOUT = 2.0   # seconds — drop reading to slow client beyond this


class Broadcaster:
    """Fan-out of readings to the set of connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: dict = {}

    async def register(self, websocket) -> None:
        self._clients[websocket] = None   
        log.info("WebSocket client registered. Total: %d", len(self._clients))

    async def unregister(self, websocket) -> None:
        self._clients.pop(websocket, None)
        log.info("WebSocket client unregistered. Total: %d", len(self._clients))

    async def set_subscription(self, websocket, sensor_ids) -> None:
        """Replace the per-client sensor-id filter."""
        if websocket in self._clients:
            self._clients[websocket] = set(sensor_ids) if sensor_ids else None

    async def publish(self, reading: dict) -> None:
        """Push a reading to every subscribed client concurrently."""
        if not self._clients:
            return

        message = json.dumps({
            "sensor_id": reading.get("sensor_id"),
            "type":      reading.get("type"),
            "value":     reading.get("value"),
            "unit":      reading.get("unit", ""),
            "ts":        reading.get("timestamp"),
        })

        tasks = []
        for ws, subscriptions in list(self._clients.items()):
            # Check subscription filter
            if subscriptions is not None:
                if reading.get("sensor_id") not in subscriptions:
                    continue
            tasks.append(self._send_one(ws, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_one(self, ws, message: str) -> None:
        try:
            await asyncio.wait_for(ws.send(message), timeout=SEND_TIMEOUT)
        except asyncio.TimeoutError:
            log.debug("Slow WebSocket client — reading dropped")
        except Exception as exc:
            log.debug("WebSocket send error: %s", exc)
            await self.unregister(ws)
