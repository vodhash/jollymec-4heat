# Copyright 2026 vodhash
"""The Jolly Mec 4HEAT integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import JollyMec4HeatApi
from .const import CONF_DEVICE_ID, CONF_PIN, PLATFORMS
from .coordinator import JollyMec4HeatCoordinator

type JollyMec4HeatConfigEntry = ConfigEntry[JollyMec4HeatCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: JollyMec4HeatConfigEntry) -> bool:
    api = JollyMec4HeatApi(
        async_get_clientsession(hass),
        entry.data[CONF_DEVICE_ID],
        entry.data[CONF_PIN],
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = JollyMec4HeatCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JollyMec4HeatConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
