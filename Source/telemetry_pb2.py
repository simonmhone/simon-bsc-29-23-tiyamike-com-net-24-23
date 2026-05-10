"""
telemetry_pb2.py — hand-written Protobuf stubs.

Avoids needing protoc at runtime.  The on-wire encoding is identical to
what `protoc --python_out=.` would produce for proto/telemetry.proto.
"""
from __future__ import annotations

import struct


# ---------------------------------------------------------------------------
# Minimal varint helpers
# ---------------------------------------------------------------------------

def _encode_varint(value: int) -> bytes:
    bits = []
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            bits.append(b | 0x80)
        else:
            bits.append(b)
            break
    return bytes(bits)


def _decode_varint(buf: bytes, pos: int):
    result, shift = 0, 0
    while pos < len(buf):
        b = buf[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    raise ValueError("Truncated varint")


# ---------------------------------------------------------------------------
# Wire-type helpers
# ---------------------------------------------------------------------------
WIRE_VARINT   = 0
WIRE_64BIT    = 1
WIRE_LEN      = 2
WIRE_32BIT    = 5


def _field_tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _encode_string(field_number: int, s: str) -> bytes:
    encoded = s.encode()
    return _field_tag(field_number, WIRE_LEN) + _encode_varint(len(encoded)) + encoded


def _encode_double(field_number: int, v: float) -> bytes:
    return _field_tag(field_number, WIRE_64BIT) + struct.pack("<d", v)


# ---------------------------------------------------------------------------
# Reading message
# ---------------------------------------------------------------------------

class Reading:
    """
    message Reading {
      string sensor_id  = 1;
      string type       = 2;
      double value      = 3;
      double timestamp  = 4;
      string unit       = 5;
    }
    """

    def __init__(self, sensor_id="", type="", value=0.0, timestamp=0.0, unit=""):
        self.sensor_id = sensor_id
        self.type      = type
        self.value     = value
        self.timestamp = timestamp
        self.unit      = unit

    def SerializeToString(self) -> bytes:
        out = b""
        if self.sensor_id: out += _encode_string(1, self.sensor_id)
        if self.type:       out += _encode_string(2, self.type)
        if self.value:      out += _encode_double(3, self.value)
        if self.timestamp:  out += _encode_double(4, self.timestamp)
        if self.unit:       out += _encode_string(5, self.unit)
        return out

    @classmethod
    def FromString(cls, data: bytes) -> "Reading":
        obj = cls()
        pos = 0
        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_number = tag >> 3
            wire_type    = tag & 0x07
            if wire_type == WIRE_LEN:
                length, pos = _decode_varint(data, pos)
                payload = data[pos:pos+length]; pos += length
                if field_number == 1: obj.sensor_id = payload.decode()
                elif field_number == 2: obj.type    = payload.decode()
                elif field_number == 5: obj.unit    = payload.decode()
            elif wire_type == WIRE_64BIT:
                payload = data[pos:pos+8]; pos += 8
                v = struct.unpack("<d", payload)[0]
                if field_number == 3: obj.value     = v
                elif field_number == 4: obj.timestamp = v
            else:
                break  # unknown wire type — skip
        return obj

    def to_dict(self) -> dict:
        return {
            "sensor_id": self.sensor_id,
            "type":      self.type,
            "value":     self.value,
            "timestamp": self.timestamp,
            "unit":      self.unit,
        }


# ---------------------------------------------------------------------------
# SensorRegistration message
# ---------------------------------------------------------------------------

class SensorRegistration:
    """
    message SensorRegistration {
      string sensor_id        = 1;
      string type             = 2;
      string location         = 3;
      double interval_seconds = 4;
    }
    """

    def __init__(self, sensor_id="", type="", location="", interval_seconds=0.0):
        self.sensor_id        = sensor_id
        self.type             = type
        self.location         = location
        self.interval_seconds = interval_seconds

    def SerializeToString(self) -> bytes:
        out = b""
        if self.sensor_id:        out += _encode_string(1, self.sensor_id)
        if self.type:             out += _encode_string(2, self.type)
        if self.location:         out += _encode_string(3, self.location)
        if self.interval_seconds: out += _encode_double(4, self.interval_seconds)
        return out

    @classmethod
    def FromString(cls, data: bytes) -> "SensorRegistration":
        obj = cls()
        pos = 0
        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_number = tag >> 3
            wire_type    = tag & 0x07
            if wire_type == WIRE_LEN:
                length, pos = _decode_varint(data, pos)
                payload = data[pos:pos+length]; pos += length
                if field_number == 1: obj.sensor_id = payload.decode()
                elif field_number == 2: obj.type     = payload.decode()
                elif field_number == 3: obj.location = payload.decode()
            elif wire_type == WIRE_64BIT:
                payload = data[pos:pos+8]; pos += 8
                v = struct.unpack("<d", payload)[0]
                if field_number == 4: obj.interval_seconds = v
            else:
                break
        return obj

    def to_dict(self) -> dict:
        return {
            "sensor_id":        self.sensor_id,
            "type":             self.type,
            "location":         self.location,
            "interval_seconds": self.interval_seconds,
        }
