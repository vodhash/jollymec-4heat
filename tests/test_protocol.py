"""Tests for the 4HEAT 2ways decoding and command encoding."""
import json
import pathlib
import sys

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "jollymec_4heat")
)

import protocol  # noqa: E402

# Frames captured live from an insert in standby, room 20 C.
MAIN = "10000100000b00072217001422000000018800"
FLUE = "12ffff001d000000000100000000000000"
ROOM = "12fff70014000000000100000000000000"
POWER = "0e016c00020001000700000001016c0007"
SETPOINT = "12005a0014000a00280000000100000000"
INFO81 = "0c81013200011000640b0000001400"


def test_decode_main_values():
    assert protocol.decode_frame(MAIN) == {
        "kind": 16,
        "temp_secondary": 0,
        "state": 11,
        "error": 0,
        "temp_main": 20,
        "decimals": 0,
    }


def test_decode_registers():
    assert protocol.decode_frame(FLUE)["value"] == 29
    assert protocol.decode_frame(ROOM)["value"] == 20
    assert protocol.decode_frame(POWER)["value"] == 2
    setpoint = protocol.decode_frame(SETPOINT)
    assert (setpoint["register"], setpoint["value"], setpoint["min"], setpoint["max"]) == (
        0x5A,
        20,
        10,
        40,
    )


def test_decode_info81():
    info = protocol.decode_frame(INFO81)
    assert info["power_level"] == "2"
    assert info["setpoint"] == 20


def test_signed():
    assert protocol.decode_frame("12fff7fffb000000000100000000000000")["value"] == -5


def test_command_write_setpoint_matches_hardware():
    # Validated against the stove: 20 -> 21 was applied with this exact payload.
    assert protocol.command_write(SETPOINT, 21) == [
        "2WC",
        "1",
        "0512005a0015000a00280000000100",
    ]


def test_command_write_power():
    # Combustion power (type 0e) frame, set to P4.
    assert protocol.command_write(POWER, 4) == ["2WC", "1", "050e016c0004"]


def test_command_power():
    device_map = protocol.DeviceMap(
        protocol="2ways",
        registers=(),
        menu_params=(),
        states={},
        errors=(),
        setpoint_comando=None,
        power_on="05040000",
        power_off="05050000",
        unblock="05050000",
    )
    assert protocol.command_power(device_map, True) == ["2WC", "1", "05040000"]
    assert protocol.command_power(device_map, False) == ["2WC", "1", "05050000"]


def test_parse_menu_params():
    params = protocol._parse_menu_params(
        {
            "comandi_menu": [
                {"comando": "", "descrizione_en": "Root"},
                {
                    "comando": "030E016C",
                    "descrizione_en": "Combustion",
                    "visible": True,
                    "cenums": [
                        {"val": 1, "descrizione_en": "P1"},
                        {"val": 7, "descrizione_en": "Auto"},
                    ],
                },
                {"comando": "03120058", "descrizione_en": "Remote Room 1", "visible": False},
            ]
        }
    )
    assert [p.comando for p in params] == ["030E016C", "03120058"]
    assert params[0].options == {1: "P1", 7: "Auto"}
    assert (params[0].key, params[0].visible) == ("combustion", True)
    assert params[1].options is None


def test_decode_summary():
    device_map = protocol.DeviceMap(
        protocol="2ways",
        registers=(
            protocol.RegisterSpec("0310", "mainvalues", "MAINVALUES", None, 1),
            protocol.RegisterSpec("0312FFFF", "temperatura_fumi", "Temperatura Fumi", "°C", 1),
            protocol.RegisterSpec("0312005A", "termostato", "Termostato Ambiente", "°C", 1),
        ),
        menu_params=(),
        states={0: "OFF", 11: "STANDBY"},
        errors=("----", "Er01"),
        setpoint_comando="0312005A",
        power_on="05040000",
        power_off="05050000",
        unblock="05050000",
    )
    summary = {
        "IsOnline": True,
        "Name": "Insert",
        "FirmwareVersion": 2,
        "FirmwareRevision": 11,
        "LastMessageReceived": json.dumps(
            {"TimeStamp": "2026-10-25T22:00:00", "Values": [MAIN, FLUE, SETPOINT]}
        ),
    }
    state = protocol.decode_summary(device_map, summary)
    assert state.online is True
    assert state.state == "STANDBY"
    assert state.error == "----"
    assert state.room_temperature == 20
    assert state.flue_temperature == 29
    assert (state.setpoint, state.setpoint_min, state.setpoint_max) == (20, 10, 40)
    assert state.setpoint_frame == SETPOINT
    assert state.firmware == "2.11"
    reading = state.readings["0312005A"]
    assert (reading.value, reading.minimum, reading.maximum, reading.frame) == (20, 10, 40, SETPOINT)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name} ok")
