"""Entry point for the telemetry server.

Runs ALL three services in one process so readings flow directly
to the WebSocket dashboard:

  TCP ingest (port 9000)  →  storage + broadcaster
  REST API   (port 8080)  ←  storage
  WebSocket  (port 8765)  ←  broadcaster

Run with:
    python -m server
"""
from __future__ import annotations

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.storage    import Storage
from server.tcp_ingest import start_tcp_server
from server.rest_api   import build_app
from aiohttp import web
import websockets
import wss.handler as handler_module
from wss.broadcaster import Broadcaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
log = logging.getLogger("server")

TCP_HOST  = "127.0.0.1"
TCP_PORT  = 9000
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8080
WSS_HOST  = "127.0.0.1"
WSS_PORT  = 8765


async def main() -> None:
    # Shared storage
    storage = Storage()

    # Broadcaster — live readings fan-out to WebSocket clients
    broadcaster = Broadcaster()
    handler_module._broadcaster = broadcaster

    # 1. TCP ingest — sensors push Protobuf readings here
    tcp_server = await start_tcp_server(
        TCP_HOST, TCP_PORT,
        storage=storage,
        broadcaster=broadcaster,   # ← readings are published here
    )

    # 2. REST API
    app = build_app(storage)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HTTP_HOST, HTTP_PORT)
    await site.start()

    # 3. WebSocket live feed
    wss_server = await websockets.serve(handler_module.live, WSS_HOST, WSS_PORT)

    log.info("TCP ingest  listening on tcp://%s:%d",  TCP_HOST,  TCP_PORT)
    log.info("REST API    listening on http://%s:%d", HTTP_HOST, HTTP_PORT)
    log.info("WebSocket   listening on ws://%s:%d",   WSS_HOST,  WSS_PORT)
    log.info("Open dashboard.html in your browser then press Ctrl-C to stop.")

    try:
        await asyncio.Event().wait()   # run forever
    except asyncio.CancelledError:
        pass
    finally:
        tcp_server.close()
        await tcp_server.wait_closed()
        wss_server.close()
        await wss_server.wait_closed()
        await runner.cleanup()
        log.info("Server stopped.")


if __name__ == "__main__":
    asyncio.run(main())
