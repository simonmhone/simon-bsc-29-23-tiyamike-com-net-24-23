"""Entry point for the sensor simulator.

Run with:
    python -m client --config config/sensors.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml
from client.simulator import SensorSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
log = logging.getLogger("client")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IoT sensor simulator")
    parser.add_argument(
        "--config",
        default="config/sensors.yaml",
        help="Path to the YAML sensor configuration file",
    )
    return parser.parse_args()


def _load_config(path: str) -> dict:
    with open(path) as fh:
        cfg = yaml.safe_load(fh)
    # Validate required keys
    if "server" not in cfg:
        raise ValueError("Config missing 'server' section")
    if not cfg["server"].get("host"):
        raise ValueError("Config missing server.host")
    if not cfg["server"].get("port"):
        raise ValueError("Config missing server.port")
    if "sensors" not in cfg or not cfg["sensors"]:
        raise ValueError("Config has no sensors")
    return cfg


async def main() -> None:
    args   = _parse_args()
    config = _load_config(args.config)

    host = config["server"]["host"]
    port = int(config["server"]["port"])

    tasks = []
    for sensor_cfg in config["sensors"]:
        sid      = sensor_cfg["id"]
        stype    = sensor_cfg["type"]
        interval = float(sensor_cfg["interval_seconds"])
        value_range = None
        if "range" in sensor_cfg:
            lo, hi = sensor_cfg["range"]
            value_range = (float(lo), float(hi))

        sim = SensorSimulator(
            sensor_id        = sid,
            sensor_type      = stype,
            interval_seconds = interval,
            host             = host,
            port             = port,
            value_range      = value_range,
        )
        tasks.append(asyncio.create_task(sim.run(), name=f"sensor-{sid}"))
        log.info("Scheduled sensor %s (%s) every %.1fs", sid, stype, interval)

    log.info("Starting %d sensors → %s:%d", len(tasks), host, port)
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        log.info("Sensor simulator shutting down.")


if __name__ == "__main__":
    asyncio.run(main())
