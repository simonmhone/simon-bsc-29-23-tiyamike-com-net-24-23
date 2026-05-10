"""
wss/handler.py — WebSocket connection handler at /live.

Protocol (JSON frames):
  Client → Server (optional):
      {"action": "subscribe", "sensors": ["sensor-a", "sensor-b"]}
  Server → Client (continuous):
      {"sensor_id": "...", "type": "...", "value": ..., "unit": "...", "ts": ...}
"""
from __future__ import annotations

import asyncio
import json
import logging

log = logging.getLogger(__name__)

_broadcaster = None   


async def live(websocket, path: str = "/live") -> None:
    """Handle one WebSocket client connection."""
    await _broadcaster.register(websocket)
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.debug("Non-JSON message from client: %r", raw)
                continue

            if msg.get("action") == "subscribe":
                sensor_ids = msg.get("sensors", [])
                await _broadcaster.set_subscription(websocket, sensor_ids)
                log.info("Client subscribed to: %s", sensor_ids)
            else:
                log.debug("Unknown action: %s", msg.get("action"))
    except Exception as exc:
        log.debug("WebSocket client error: %s", exc)
    finally:
        await _broadcaster.unregister(websocket)
