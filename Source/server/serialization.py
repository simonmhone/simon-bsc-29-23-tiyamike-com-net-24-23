"""
server/serialization.py — Content negotiation for the REST API.

Parses the Accept header and serializes the response payload to the
chosen format: JSON (default), XML, or YAML.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import yaml
from aiohttp import web


_SUPPORTED = [
    "application/json",
    "application/xml",
    "text/xml",
    "application/yaml",
    "text/yaml",
]


def negotiate(request: web.Request) -> str:
    """Return the best matching media type for *request*.

    Parses quality values (q=…).  Defaults to application/json.
    """
    accept_header = request.headers.get("Accept", "*/*")
    candidates: list[tuple[float, str]] = []
    for part in accept_header.split(","):
        part = part.strip()
        if ";q=" in part:
            media, q = part.split(";q=", 1)
            try:
                quality = float(q.strip())
            except ValueError:
                quality = 1.0
        elif ";" in part:
            media = part.split(";")[0]
            quality = 1.0
        else:
            media = part
            quality = 1.0
        candidates.append((quality, media.strip()))
    candidates.sort(key=lambda x: -x[0])

    for _, media in candidates:
        if media in ("*/*", "application/*"):
            return "application/json"
        for supported in _SUPPORTED:
            if media == supported:
                return supported

    return "application/json"


def _dict_to_xml(tag: str, data) -> ET.Element:
    """Recursively convert a dict/list to an XML element."""
    elem = ET.Element(tag)
    if isinstance(data, dict):
        for key, val in data.items():
            child = _dict_to_xml(key, val)
            elem.append(child)
    elif isinstance(data, list):
        for item in data:
            child = _dict_to_xml("item", item)
            elem.append(child)
    else:
        elem.text = str(data) if data is not None else ""
    return elem


def serialize(payload, media_type: str) -> tuple[bytes, str]:
    """Serialize *payload* (dict or list) and return (bytes, content_type)."""
    if media_type in ("application/xml", "text/xml"):
        root = _dict_to_xml("response", payload)
        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode").encode(), media_type

    if media_type in ("application/yaml", "text/yaml"):
        return yaml.dump(payload, default_flow_style=False).encode(), media_type

    return json.dumps(payload, default=str).encode(), "application/json"
