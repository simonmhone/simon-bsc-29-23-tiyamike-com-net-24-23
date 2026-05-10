"""
server/tcp_ingest.py — Asynchronous TCP listener for sensor connections.

Framing: 4-byte big-endian length prefix followed by a Protobuf payload.
Each payload is a serialised telemetry_pb2.Reading.

On receipt:
  1. Decode the Protobuf message.
  2. Persist via the storage layer.
  3. Publish to the live broadcaster (if one is configured).
"""
from __future__ import annotations

import asyncio
import logging
import struct
import sys
import os

# Allow imports from Source/ root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import telemetry_pb2

log = logging.getLogger(__name__)

_storage     = None   # set by start_tcp_server
_broadcaster = None   


async def handle_sensor(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    """Handle one sensor connection until it closes."""
    peer = writer.get_extra_info("peername")
    log.info("Sensor connected from %s", peer)

    try:
        while True:
            header = await reader.readexactly(4)
            length = struct.unpack(">I", header)[0]

            if length == 0 or length > 1_000_000:
                log.warning("Implausible frame length %d from %s — skipping", length, peer)
                continue

            payload = await reader.readexactly(length)

            try:
                reading_msg = telemetry_pb2.Reading.FromString(payload)
            except Exception as exc:
                log.warning("Malformed Protobuf frame from %s: %s", peer, exc)
                continue

            reading_dict = reading_msg.to_dict()
            if _storage:
                sensor = await _storage.get_sensor(reading_dict["sensor_id"])
                if sensor is None:
                    await _storage.add_sensor({
                        "sensor_id": reading_dict["sensor_id"],
                        "type":      reading_dict["type"],
                        "location":  "",
                        "interval_seconds": 0,
                    })
                await _storage.add_reading(reading_dict)

            # Forward to WebSocket broadcaster
            if _broadcaster:
                try:
                    await _broadcaster.publish(reading_dict)
                except Exception as exc:
                    log.debug("Broadcaster publish error: %s", exc)

    except asyncio.IncompleteReadError:
        log.info("Sensor %s disconnected", peer)
    except Exception as exc:
        log.error("Unexpected error handling sensor %s: %s", peer, exc)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def start_tcp_server(
    host: str,
    port: int,
    storage=None,
    broadcaster=None,
) -> asyncio.AbstractServer:
    """Start the TCP ingest server listening on (host, port)."""
    global _storage, _broadcaster
    _storage     = storage
    _broadcaster = broadcaster

    server = await asyncio.start_server(handle_sensor, host, port)
    log.info("TCP ingest listening on %s:%d", host, port)
    return server
