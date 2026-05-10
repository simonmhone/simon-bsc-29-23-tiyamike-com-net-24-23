"""
server/rest_api.py — REST API for the telemetry server.

Endpoints:
    GET    /sensors                     list registered sensors
    GET    /sensors/{id}/readings       historical readings (?from=&to=)
    POST   /sensors                     register a new sensor
    DELETE /sensors/{id}                remove a sensor

Content negotiation via Accept header → JSON / XML / YAML.
Sessions tracked via a "session_id" cookie.
"""
from __future__ import annotations

import json
import uuid
import yaml
import logging
from aiohttp import web

from server.serialization import negotiate, serialize

log = logging.getLogger(__name__)

SESSION_COOKIE = "session_id"

@web.middleware
async def session_cookie_middleware(request: web.Request, handler):
    """Assign a session cookie on first contact; echo it back every time."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        session_id = str(uuid.uuid4())
        request["new_session"] = True
    else:
        request["new_session"] = False
    request["session_id"] = session_id

    response = await handler(request)

    if request["new_session"]:
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=86400 * 30,
            samesite="Lax",
        )
    return response

def _respond(request: web.Request, payload, status: int = 200) -> web.Response:
    media_type = negotiate(request)
    body, content_type = serialize(payload, media_type)
    return web.Response(status=status, body=body, content_type=content_type)


async def _parse_body(request: web.Request) -> dict:
    """Parse request body; respect Content-Type (JSON / YAML)."""
    ct = request.content_type or "application/json"
    text = await request.text()
    if "yaml" in ct:
        return yaml.safe_load(text) or {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}

# Route handlers

async def list_sensors(request: web.Request) -> web.Response:
    storage = request.app["storage"]
    sensors = await storage.list_sensors()
    return _respond(request, sensors)


async def get_readings(request: web.Request) -> web.Response:
    storage  = request.app["storage"]
    sensor_id = request.match_info["id"]

    sensor = await storage.get_sensor(sensor_id)
    if sensor is None:
        return web.Response(status=404, text=f"Sensor '{sensor_id}' not found")

    from_ts = request.rel_url.query.get("from")
    to_ts   = request.rel_url.query.get("to")

    try:
        from_ts = float(from_ts) if from_ts is not None else None
        to_ts   = float(to_ts)   if to_ts   is not None else None
    except ValueError:
        return web.Response(status=400, text="'from' and 'to' must be Unix timestamps")

    readings = await storage.get_readings(sensor_id, from_ts, to_ts)
    return _respond(request, readings)


async def register_sensor(request: web.Request) -> web.Response:
    storage = request.app["storage"]
    body    = await _parse_body(request)

    sensor_id = body.get("sensor_id")
    if not sensor_id:
        return web.Response(status=400, text="'sensor_id' is required")

    sensor = {
        "sensor_id":        sensor_id,
        "type":             body.get("type", "unknown"),
        "location":         body.get("location", ""),
        "interval_seconds": body.get("interval_seconds", 0),
    }
    await storage.add_sensor(sensor)
    log.info("Registered sensor %s via REST", sensor_id)

    media_type = negotiate(request)
    body_bytes, content_type = serialize(sensor, media_type)
    return web.Response(
        status=201,
        body=body_bytes,
        content_type=content_type,
        headers={"Location": f"/sensors/{sensor_id}"},
    )


async def delete_sensor(request: web.Request) -> web.Response:
    storage   = request.app["storage"]
    sensor_id = request.match_info["id"]

    sensor = await storage.get_sensor(sensor_id)
    if sensor is None:
        return web.Response(status=404, text=f"Sensor '{sensor_id}' not found")

    await storage.remove_sensor(sensor_id)
    log.info("Deleted sensor %s via REST", sensor_id)
    return web.Response(status=204)

def build_app(storage) -> web.Application:
    """Construct and return the aiohttp Application."""
    app = web.Application(middlewares=[session_cookie_middleware])
    app["storage"] = storage

    app.router.add_get   ("/sensors",              list_sensors)
    app.router.add_get   ("/sensors/{id}/readings", get_readings)
    app.router.add_post  ("/sensors",              register_sensor)
    app.router.add_delete("/sensors/{id}",         delete_sensor)

    return app
