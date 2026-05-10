"""Entry point for the WebSocket live-feed server.

Run with:
    python -m wss

The WSS server and the telemetry server share readings via an asyncio Queue
written to a shared file-based IPC channel — or, in single-machine
deployments, by importing a shared in-process queue.

For this prototype, the broadcaster is connected to the TCP ingest server
by monkey-patching server.tcp_ingest._broadcaster after both modules are
imported in the same process.  See README.md for the multi-process option.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import websockets
from wss.broadcaster import Broadcaster
import wss.handler as handler_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
log = logging.getLogger("wss")

WSS_HOST = "127.0.0.1"
WSS_PORT = 8765


async def main() -> None:
    broadcaster = Broadcaster()
    handler_module._broadcaster = broadcaster

    log.info("WebSocket live-feed starting on ws://%s:%d/live", WSS_HOST, WSS_PORT)

    async with websockets.serve(handler_module.live, WSS_HOST, WSS_PORT):
        log.info("WebSocket server ready. Press Ctrl-C to stop.")
        await asyncio.Event().wait()   # run forever


if __name__ == "__main__":
    asyncio.run(main())
