# Copyright 2026 vodhash
"""Heat demand switch for Jolly Mec 4HEAT.

ON pushes the stove setpoint to its maximum so the stove runs; OFF pushes it to
its minimum so the stove drops to its native STANDBY without a full shutdown.
Point a Home Assistant generic_thermostat at this switch to get an adjustable
delta driven by your own temperature sensors.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import JollyMec4HeatConfigEntry
from .entity import JollyMec4HeatEntity
from .protocol import command_write


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JollyMec4HeatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.device_map.setpoint_comando:
        async_add_entities([HeatDemandSwitch(coordinator)])


class HeatDemandSwitch(JollyMec4HeatEntity, SwitchEntity):
    _attr_name = "Heat demand"
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "heat_demand")

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.setpoint_frame is not None

    @property
    def is_on(self) -> bool | None:
        state = self.coordinator.data
        if state.setpoint is None or state.setpoint_max is None:
            return None
        return state.setpoint >= state.setpoint_max

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._apply(self.coordinator.data.setpoint_max)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._apply(self.coordinator.data.setpoint_min)

    async def _apply(self, setpoint: float | None) -> None:
        state = self.coordinator.data
        if setpoint is None or state.setpoint_frame is None:
            return
        # shortcut: integer setpoint (multiplier 1, no decimals); scale by the
        # register decimals here if a future device reports a fractional setpoint.
        await self.coordinator.api.async_send_command(
            command_write(state.setpoint_frame, int(setpoint))
        )
        await self.coordinator.async_request_refresh()
