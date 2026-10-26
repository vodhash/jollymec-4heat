# Copyright 2026 vodhash
"""Climate entity mirroring the stove's own thermostat.

Target temperature is the stove setpoint, OFF/HEAT map to the real extinguish and
ignition commands. For a custom delta thermostat use the Heat demand switch with a
generic_thermostat instead, so the stove stays in its gentle STANDBY.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import JollyMec4HeatConfigEntry
from .entity import JollyMec4HeatEntity
from .protocol import (
    STATES_FAULT,
    STATES_IDLE,
    STATES_OFF,
    OptimisticValue,
    command_power,
    command_write,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JollyMec4HeatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([StoveClimate(entry.runtime_data)])


class StoveClimate(JollyMec4HeatEntity, ClimateEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 1

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "thermostat")
        self._optimistic_temp = OptimisticValue()
        self._optimistic_mode = OptimisticValue()

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.room_temperature

    @property
    def target_temperature(self) -> float | None:
        return self._optimistic_temp.resolve(self.coordinator.data.setpoint)

    @property
    def min_temp(self) -> float:
        return self.coordinator.data.setpoint_min or 10

    @property
    def max_temp(self) -> float:
        return self.coordinator.data.setpoint_max or 40

    @property
    def hvac_mode(self) -> HVACMode:
        # OFF while extinguishing too, so pressing Arret reads OFF at once during the
        # several minute shutdown instead of snapping back to heat.
        actual = HVACMode.OFF if self.coordinator.data.state_code in STATES_OFF else HVACMode.HEAT
        return self._optimistic_mode.resolve(actual)

    @property
    def hvac_action(self) -> HVACAction:
        code = self.coordinator.data.state_code
        if code in STATES_OFF or code in STATES_FAULT:
            return HVACAction.OFF
        if code in STATES_IDLE:
            return HVACAction.IDLE
        return HVACAction.HEATING

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        frame = self.coordinator.data.setpoint_frame
        if temperature is None or frame is None:
            return
        # shortcut: integer setpoint (multiplier 1, no decimals); scale here if a
        # future device reports a fractional setpoint.
        value = int(temperature)
        self._optimistic_temp.set(value)
        self.async_write_ha_state()
        await self.coordinator.api.async_send_command(command_write(frame, value))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self._optimistic_mode.set(hvac_mode)
        self.async_write_ha_state()
        await self.coordinator.api.async_send_command(
            command_power(self.coordinator.device_map, hvac_mode == HVACMode.HEAT)
        )
        await self.coordinator.async_request_refresh()
