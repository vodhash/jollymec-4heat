# Copyright 2026 vodhash
"""Number entities for the stove's numeric menu parameters.

One entity per settable menu parameter without a fixed list of choices (for
example the remote room temperatures). These are hidden in the app, so they are
added disabled by default. Min and max come from the register's own report.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import JollyMec4HeatConfigEntry
from .entity import JollyMec4HeatEntity
from .protocol import MenuParam, command_write


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JollyMec4HeatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    readings = coordinator.data.readings
    async_add_entities(
        MenuNumber(coordinator, param)
        for param in coordinator.device_map.menu_params
        if not param.options and param.comando.upper() in readings
    )


class MenuNumber(JollyMec4HeatEntity, NumberEntity):
    _attr_native_step = 1

    def __init__(self, coordinator, param: MenuParam) -> None:
        super().__init__(coordinator, f"menu_{param.key}")
        self._param = param
        self._attr_name = param.name
        self._attr_entity_registry_enabled_default = param.visible

    def _reading(self):
        return self.coordinator.data.readings.get(self._param.comando.upper())

    @property
    def available(self) -> bool:
        return super().available and self._reading() is not None

    @property
    def native_min_value(self) -> float:
        reading = self._reading()
        return reading.minimum if reading and reading.minimum is not None else 0

    @property
    def native_max_value(self) -> float:
        reading = self._reading()
        return reading.maximum if reading and reading.maximum is not None else 100

    @property
    def native_value(self) -> float | None:
        reading = self._reading()
        return reading.value if reading else None

    async def async_set_native_value(self, value: float) -> None:
        reading = self._reading()
        if reading is None:
            return
        await self.coordinator.api.async_send_command(command_write(reading.frame, int(value)))
        await self.coordinator.async_request_refresh()
