# Copyright 2026 vodhash
"""Constants for the Jolly Mec 4HEAT integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform

DOMAIN = "jollymec_4heat"
LOGGER = logging.getLogger(__package__)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_DEVICE_ID = "device_id"
CONF_PIN = "pin"

DEFAULT_PIN = "000000"
DEFAULT_SCAN_INTERVAL = 60

MANUFACTURER = "Tiemme Elettronica"
