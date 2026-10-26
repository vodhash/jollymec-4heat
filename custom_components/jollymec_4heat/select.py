# Copyright 2026 vodhash
"""Select entities for the stove's enumerated menu parameters.

One entity per settable menu parameter that exposes a list of choices (for
example combustion power P1-P6/Auto). Visible-in-app parameters are enabled by
default; the hidden ones (canalization, temperature source selector) are added
disabled so they stay out of the way until wanted.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import JollyMec4HeatConfigEntry
from .entity import JollyMec4HeatEntity
from .protocol import MenuParam, OptimisticValue, command_write


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JollyMec4HeatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    readings = coordinator.data.readings
    async_add_entities(
        MenuSelect(coordinator, param)
        for param in coordinator.device_map.menu_params
        if param.options and param.comando.upper() in readings
    )


class MenuSelect(JollyMec4HeatEntity, SelectEntity):
    def __init__(self, coordinator, param: MenuParam) -> None:
        super().__init__(coordinator, f"menu_{param.key}")
        self._param = param
        self._label_by_value = param.options or {}
        self._value_by_label = {label: value for value, label in self._label_by_value.items()}
        self._attr_name = param.name
        self._attr_options = list(self._label_by_value.values())
        self._attr_entity_registry_enabled_default = param.visible
        self._optimistic = OptimisticValue()

    def _reading(self):
        return self.coordinator.data.readings.get(self._param.comando.upper())

    @property
    def available(self) -> bool:
        return super().available and self._reading() is not None

    @property
    def current_option(self) -> str | None:
        reading = self._reading()
        if reading is None:
            return None
        return self._label_by_value.get(self._optimistic.resolve(int(reading.value)))

    async def async_select_option(self, option: str) -> None:
        reading = self._reading()
        if reading is None or option not in self._value_by_label:
            return
        value = self._value_by_label[option]
        self._optimistic.set(value)
        self.async_write_ha_state()
        await self.coordinator.api.async_send_command(command_write(reading.frame, value))
        await self.coordinator.async_request_refresh()
