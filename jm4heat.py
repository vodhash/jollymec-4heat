#!/usr/bin/env python3
# Copyright 2026 vodhash
"""Standalone read-only CLI for the 4HEAT cloud, reusing the integration decoder.

Reads device state with no account. Set JM_DEVICE_ID (and JM_PIN if not 000000).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.request

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent / "custom_components" / "jollymec_4heat")
)

from protocol import decode_summary, parse_device_map  # noqa: E402

BASE = "https://wifi4heat.azurewebsites.net"


def _get(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "jm4heat/0"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed https host)
        return json.load(response)


def read_state(device_id: str, pin: str):
    device_map = parse_device_map(_get(f"{BASE}/api/Devices/FileMap?pin={pin}&id={device_id}"))
    summary = _get(f"{BASE}/api/devices/summary?ids={device_id}")[0]
    return decode_summary(device_map, summary)


def main() -> int:
    device_id = os.environ.get("JM_DEVICE_ID")
    pin = os.environ.get("JM_PIN", "000000")
    if not device_id:
        print("set JM_DEVICE_ID (and JM_PIN if not 000000)", file=sys.stderr)
        return 2
    state = read_state(device_id, pin)
    print(f"{'online' if state.online else 'offline'}  {state.name}  fw {state.firmware}  {state.timestamp}")
    print(f"state   : {state.state} ({state.state_code})")
    print(f"error   : {state.error or 'none'} ({state.error_code})")
    print(f"room    : {state.room_temperature} C")
    print(f"flue    : {state.flue_temperature} C")
    print(f"setpoint: {state.setpoint} C  [{state.setpoint_min}..{state.setpoint_max}]")
    for key, value in state.values.items():
        print(f"  {key:28} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
