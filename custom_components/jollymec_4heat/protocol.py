# Copyright 2026 vodhash
"""Pure decoding and command encoding for the 4HEAT "2ways" cloud protocol.

No Home Assistant or network imports here so the logic stays unit testable.
State is read from the device "summary" message, whose "Values" are hex frames.
Frame layout (offsets in hex chars) follows the vendor app's SERVIZI2W.estraivalori.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

PROTOCOL_2WAYS = "2ways"

_FLUE_REGISTER_SUFFIX = "FFFF"


def _signed16(value: int) -> int:
    return value - 65536 if value > 32767 else value


def _at(frame: str, start: int, length: int) -> int:
    return int(frame[start:start + length], 16)


def _slug(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", text.lower())).strip("_")


def decode_frame(frame: str) -> dict:
    """Decode one hex value frame; byte 0 is the type, rest is type specific."""
    kind = int(frame[0:2], 16)
    if kind in (18, 14):  # testout (0x12) / par_value (0x0e)
        return {
            "kind": kind,
            "register": _at(frame, 2, 4),
            "value": _signed16(_at(frame, 6, 4)),
            "min": _signed16(_at(frame, 10, 4)),
            "max": _signed16(_at(frame, 14, 4)),
            "decimals": _at(frame, 20, 2),
        }
    if kind == 16:  # main_values
        decoded = {
            "kind": 16,
            "temp_secondary": _signed16(_at(frame, 6, 4)),
            "state": _at(frame, 10, 2),
            "error": _at(frame, 12, 2),
            "temp_main": _signed16(_at(frame, 20, 4)),
            "decimals": _at(frame, 36, 2) if len(frame) > 36 else 0,
        }
        return decoded
    if kind == 12:  # state_info
        if frame[2:4] == "81":
            info = {
                "kind": "info81",
                "power_level": chr(_at(frame, 6, 2)),
                "setpoint": _at(frame, 24, 4),
            }
            if len(frame) != 28:
                info["decimals"] = _at(frame, 28, 2)
            return info
        return {"kind": "info", "text": bytes.fromhex(frame[4:]).decode("latin1")}
    if kind == 2:  # th_temp
        return {"kind": 2, "register": _at(frame, 2, 2), "value": _signed16(_at(frame, 6, 4))}
    if kind == 6:  # pw_all
        return {"kind": 6, "register": _at(frame, 2, 2), "value": _at(frame, 4, 2)}
    if kind == 34:  # th_all_2
        return {
            "kind": 34,
            "register": _at(frame, 2, 2),
            "value": _signed16(_at(frame, 10, 4)),
            "min": _signed16(_at(frame, 14, 4)),
            "max": _signed16(_at(frame, 18, 4)),
            "decimals": _at(frame, 30, 2),
        }
    return {"kind": kind, "raw": frame}


@dataclass(frozen=True)
class RegisterSpec:
    """One reported register, aligned by position with the summary Values."""

    comando: str
    key: str
    name: str
    unit: str | None
    multiplier: float


@dataclass(frozen=True)
class MenuParam:
    """A settable parameter from the device menu (comandi_menu)."""

    comando: str
    key: str
    name: str
    options: dict[int, str] | None
    visible: bool


@dataclass
class Reading:
    """Current decoded value of a register plus its raw frame for writes."""

    value: float
    minimum: float | None
    maximum: float | None
    frame: str


@dataclass(frozen=True)
class DeviceMap:
    protocol: str
    registers: tuple[RegisterSpec, ...]
    menu_params: tuple[MenuParam, ...]
    states: dict[int, str]
    errors: tuple[str, ...]
    setpoint_comando: str | None
    power_on: str
    power_off: str
    unblock: str

    @property
    def is_supported(self) -> bool:
        return self.protocol == PROTOCOL_2WAYS


@dataclass
class StoveState:
    online: bool
    name: str
    firmware: str
    timestamp: str
    state_code: int
    state: str
    error_code: int
    error: str | None
    room_temperature: float | None
    flue_temperature: float | None
    setpoint: float | None
    setpoint_min: float | None
    setpoint_max: float | None
    setpoint_frame: str | None
    values: dict[str, float] = field(default_factory=dict)
    readings: dict[str, Reading] = field(default_factory=dict)


def _parse_menu_params(filemap: dict) -> tuple[MenuParam, ...]:
    params = []
    for entry in filemap.get("comandi_menu", []):
        comando = entry.get("comando")
        if not comando:
            continue
        name = entry.get("descrizione_en") or entry.get("descrizione_it") or comando
        cenums = entry.get("cenums")
        options = (
            {item["val"]: (item.get("descrizione_en") or str(item["val"])) for item in cenums}
            if cenums
            else None
        )
        params.append(
            MenuParam(comando, _slug(name) or comando, name, options, bool(entry.get("visible")))
        )
    return tuple(params)


def parse_device_map(filemap: dict) -> DeviceMap:
    registers = []
    for entry in filemap.get("comandi_log", []):
        if not entry.get("flag_server"):
            continue
        number, _, label = (entry.get("cod_comando") or "").partition("_")
        name = label or number
        try:
            multiplier = float(entry.get("moltiplicatore") or 1)
        except (TypeError, ValueError):
            multiplier = 1.0
        registers.append(RegisterSpec(entry["comando"], _slug(name) or entry["comando"],
                                      name, entry.get("unita") or None, multiplier))
    states = {
        state["val"]: state.get("descrizione_en") or state.get("descrizione_it") or str(state["val"])
        for state in filemap.get("lingue_stati", [])
        if state.get("val") is not None
    }
    errors = tuple(error.get("descrizione_en") or "" for error in filemap.get("codici_errori", []))
    on_off = filemap.get("comandi_on_off", {})
    return DeviceMap(
        protocol=filemap.get("comunicazione", ""),
        registers=tuple(registers),
        menu_params=_parse_menu_params(filemap),
        states=states,
        errors=errors,
        setpoint_comando=(filemap.get("comandi_term_princ") or {}).get("comando") or None,
        power_on=on_off.get("accensione", ""),
        power_off=on_off.get("spegnimento", ""),
        unblock=on_off.get("sblocco", ""),
    )


def _scale(value: int, multiplier: float, decimals: int) -> float:
    scaled = value * multiplier
    return scaled / (10 ** decimals) if decimals else scaled


def decode_summary(device_map: DeviceMap, summary: dict) -> StoveState:
    message = json.loads(summary["LastMessageReceived"])
    frames = message["Values"]

    state_code = error_code = 0
    room = flue = setpoint = setpoint_min = setpoint_max = None
    setpoint_frame = None
    values: dict[str, float] = {}
    readings: dict[str, Reading] = {}

    for spec, frame in zip(device_map.registers, frames):
        decoded = decode_frame(frame)
        decimals = decoded.get("decimals", 0)
        if decoded["kind"] == 16:
            state_code = decoded["state"]
            error_code = decoded["error"]
            room = _scale(decoded["temp_main"], spec.multiplier, decimals)
        if "value" in decoded:
            value = _scale(decoded["value"], spec.multiplier, decimals)
            values[spec.key] = value
            minimum = _scale(decoded["min"], spec.multiplier, decimals) if "min" in decoded else None
            maximum = _scale(decoded["max"], spec.multiplier, decimals) if "max" in decoded else None
            readings[spec.comando.upper()] = Reading(value, minimum, maximum, frame)
        if spec.comando == device_map.setpoint_comando:
            setpoint = _scale(decoded["value"], spec.multiplier, decimals)
            setpoint_min = _scale(decoded["min"], spec.multiplier, decimals)
            setpoint_max = _scale(decoded["max"], spec.multiplier, decimals)
            setpoint_frame = frame
        if spec.comando.upper().endswith(_FLUE_REGISTER_SUFFIX):
            flue = _scale(decoded["value"], spec.multiplier, decimals)

    error = device_map.errors[error_code] if error_code < len(device_map.errors) else None
    firmware = f"{summary.get('FirmwareVersion', '')}.{summary.get('FirmwareRevision', '')}".strip(".")
    return StoveState(
        online=bool(summary.get("IsOnline")),
        name=summary.get("Name", ""),
        firmware=firmware,
        timestamp=message.get("TimeStamp", ""),
        state_code=state_code,
        state=device_map.states.get(state_code, str(state_code)),
        error_code=error_code,
        error=error or None,
        room_temperature=room,
        flue_temperature=flue,
        setpoint=setpoint,
        setpoint_min=setpoint_min,
        setpoint_max=setpoint_max,
        setpoint_frame=setpoint_frame,
        values=values,
        readings=readings,
    )


def _write_frame(read_frame: str, value: int) -> str:
    """Build a 2ways write frame from a register's read frame and a new value."""
    kind = int(read_frame[0:2], 16)
    short = f"{value & 0xFF:02x}"
    wide = f"{value & 0xFFFF:04x}"
    if kind == 1:
        return "05" + read_frame[0:10] + short + read_frame[12:]
    if kind == 6:
        return "05" + read_frame[0:4] + short + read_frame[6:10]
    if kind == 14:
        return "05" + read_frame[0:6] + wide
    if kind == 18:
        return "05" + read_frame[0:6] + wide + read_frame[10:28]
    if kind == 34:
        return "05" + read_frame[0:10] + wide + read_frame[14:]
    raise ValueError(f"unsupported frame type {kind:#x}")


def command_power(device_map: DeviceMap, turn_on: bool) -> list[str]:
    return ["2WC", "1", device_map.power_on if turn_on else device_map.power_off]


def command_unblock(device_map: DeviceMap) -> list[str]:
    return ["2WC", "1", device_map.unblock]


def command_write(frame: str, value: int) -> list[str]:
    return ["2WC", "1", _write_frame(frame, value)]
