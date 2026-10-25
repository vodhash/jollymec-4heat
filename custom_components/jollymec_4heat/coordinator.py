# Copyright 2026 vodhash
"""Polling coordinator for a Jolly Mec 4HEAT device."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import JollyMec4HeatApi, JollyMec4HeatError
from .const import CONF_DEVICE_ID, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER
from .protocol import DeviceMap, StoveState, decode_summary, parse_device_map


class JollyMec4HeatCoordinator(DataUpdateCoordinator[StoveState]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: JollyMec4HeatApi) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.api = api
        self.device_id = entry.data[CONF_DEVICE_ID]
        self.device_map: DeviceMap = None  # type: ignore[assignment]
        self.product_code = ""

    async def _async_setup(self) -> None:
        try:
            filemap = await self.api.async_get_filemap()
        except JollyMec4HeatError as err:
            raise UpdateFailed(str(err)) from err
        self.device_map = parse_device_map(filemap)
        self.product_code = filemap.get("codice_prod", "")
        if not self.device_map.is_supported:
            raise UpdateFailed(
                f"unsupported protocol '{self.device_map.protocol}', only 2ways is implemented"
            )

    async def _async_update_data(self) -> StoveState:
        try:
            summary = await self.api.async_get_summary()
        except JollyMec4HeatError as err:
            raise UpdateFailed(str(err)) from err
        return decode_summary(self.device_map, summary)
