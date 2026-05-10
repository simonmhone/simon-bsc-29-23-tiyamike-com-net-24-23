# IoT Telemetry Pipeline — Source

A working prototype of a greenhouse monitoring system for NET322 Practical Test 2.

## Project layout

```
Source/
├── proto/                  telemetry.proto  (Protobuf schema)
├── config/                 sensors.yaml     (sample sensor configuration)
├── server/                 Telemetry server — TCP ingest + REST API
│   ├── __init__.py
│   ├── __main__.py         python -m server
│   ├── storage.py          In-memory storage layer
│   ├── tcp_ingest.py       Async TCP listener for sensors
│   ├── rest_api.py         aiohttp REST API with content negotiation
│   └── serialization.py   JSON / XML / YAML serializer
├── wss/                    WebSocket server — live feed at /live
│   ├── __init__.py
│   ├── __main__.py         python -m wss
│   ├── broadcaster.py      Fan-out to connected WebSocket clients
│   └── handler.py          Per-connection coroutine
├── client/                 Sensor simulator (TCP client)
│   ├── __init__.py
│   ├── __main__.py         python -m client --config config/sensors.yaml
│   └── simulator.py        Per-sensor async simulation logic
├── telemetry_pb2.py        Hand-written Protobuf stubs (no protoc needed)
├── dashboard.html          Optional live dashboard (open in browser)
└── requirements.txt
```

## Architecture decisions

### Storage
**In-memory dicts** — chosen for simplicity and zero-setup.  The prototype
starts instantly and needs no database engine.  All data is lost on restart,
which is acceptable for a demo.  Upgrading to SQLite requires only changing
`Storage` in `server/storage.py`.

### Shared state between `server` and `wss`
The TCP ingest server and the WebSocket broadcaster must share the stream
of incoming readings.  Two deployment options:

1. **Single process** (default, simplest): Run `server/__main__.py` which
   boots both services in one event loop; `tcp_ingest` directly calls
   `broadcaster.publish()`.
2. **Two processes**: Run `python -m server` and `python -m wss`
   separately.  In this configuration the broadcaster receives readings via a
   shared asyncio Queue written to by the ingest handler.

### Slow-consumer strategy (WebSocket)
DROP — if a client's `send()` does not complete within `SEND_TIMEOUT` (2 s),
the reading is silently dropped for that client.  Fast clients are never
blocked.  The client simply misses readings during congestion, which is
acceptable for a live dashboard.

### Protobuf stubs
`telemetry_pb2.py` is a pure-Python implementation of the Protobuf wire
format for `Reading` and `SensorRegistration`.  It produces bit-identical
output to what `protoc --python_out=.` would generate, so no `protoc`
installation is required.

---

## Setup

```bash
cd Source/
pip install -r requirements.txt
```

No `protoc` step needed — `telemetry_pb2.py` is hand-written.

---

## Running

Open **three terminals**, each from the `Source/` directory.

### Terminal 1 — Telemetry server (TCP ingest + REST API)

```bash
python -m server
```

Starts:
- TCP ingest on `127.0.0.1:9000`
- REST API on `http://127.0.0.1:8080`

### Terminal 2 — WebSocket live-feed server

```bash
python -m wss
```

Starts:
- WebSocket server on `ws://127.0.0.1:8765`

### Terminal 3 — Sensor simulator

```bash
python -m client --config config/sensors.yaml
```

Reads `config/sensors.yaml` and spawns one async task per sensor.

---

## REST API

All endpoints support **server-driven content negotiation** via the `Accept`
header.  Supported media types:

| `Accept` header        | Response format |
|------------------------|-----------------|
| `application/json`     | JSON (default)  |
| `application/xml`      | XML             |
| `text/xml`             | XML             |
| `application/yaml`     | YAML            |
| `text/yaml`            | YAML            |

### List sensors

```bash
# JSON (default)
curl http://127.0.0.1:8080/sensors

# XML
curl -H "Accept: application/xml" http://127.0.0.1:8080/sensors

# YAML
curl -H "Accept: application/yaml" http://127.0.0.1:8080/sensors
```

### Historical readings

```bash
# All readings for a sensor
curl http://127.0.0.1:8080/sensors/temp-gh1/readings

# Time-windowed  (Unix timestamps)
curl "http://127.0.0.1:8080/sensors/temp-gh1/readings?from=1700000000&to=1799999999"

# XML
curl -H "Accept: application/xml" \
     "http://127.0.0.1:8080/sensors/temp-gh1/readings"
```

### Register a sensor

```bash
curl -X POST http://127.0.0.1:8080/sensors \
     -H "Content-Type: application/json" \
     -d '{"sensor_id":"manual-1","type":"temperature","location":"Test bench"}'
```

### Delete a sensor

```bash
curl -X DELETE http://127.0.0.1:8080/sensors/manual-1
```

### Sessions

A `session_id` cookie is set on the first response and echoed back on every
subsequent request.  curl handles this automatically with `-c / -b`:

```bash
curl -c cookies.txt http://127.0.0.1:8080/sensors          # sets cookie
curl -b cookies.txt http://127.0.0.1:8080/sensors          # sends cookie
```

---

## WebSocket live feed

Connect to `ws://127.0.0.1:8765`.

### Subscribe to specific sensors

After the upgrade, send a JSON subscription message:

```json
{"action": "subscribe", "sensors": ["temp-gh1", "humid-gh1"]}
```

Omit the `subscribe` message (or send an empty `sensors` list) to receive
readings from **all** sensors.

### Example with Python

```python
import asyncio, json, websockets

async def watch():
    async with websockets.connect("ws://127.0.0.1:8765") as ws:
        await ws.send(json.dumps({"action":"subscribe","sensors":["temp-gh1"]}))
        async for msg in ws:
            print(json.loads(msg))

asyncio.run(watch())
```

### Frame format (server → client)

```json
{
  "sensor_id": "temp-gh1",
  "type":      "temperature",
  "value":     23.45,
  "unit":      "°C",
  "ts":        1716300000.123
}
```

---

## Dashboard

Open `dashboard.html` directly in a browser (no server needed):

```
open Source/dashboard.html
```

Enter the WebSocket URL (`ws://127.0.0.1:8765`), click **Connect**, and watch
live sparklines update as readings arrive.

---

## Authors

- TODO: Name 1, Student ID
- TODO: Name 2, Student ID
