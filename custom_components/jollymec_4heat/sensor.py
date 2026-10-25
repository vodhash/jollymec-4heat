# Copyright 2026 vodhash
"""Sensors for Jolly Mec 4HEAT."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import JollyMec4HeatConfigEntry
from .entity import JollyMec4HeatEntity
from .protocol import StoveState


@dataclass(frozen=True, kw_only=True)
class JollyMecSensorDescription(SensorEntityDescription):
    value_fn: Callable[[StoveState], float | str | None]


CORE_SENSORS: tuple[JollyMecSensorDescription, ...] = (
    JollyMecSensorDescription(
        key="room_temperature",
        name="Room temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.room_temperature,
    ),
    JollyMecSensorDescription(
        key="flue_temperature",
        name="Flue temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.flue_temperature,
    ),
    JollyMecSensorDescription(
        key="status",
        name="Status",
        value_fn=lambda state: state.state,
    ),
    JollyMecSensorDescription(
        key="error",
        name="Error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.error or "none",
    ),
)


def _value_getter(key: str) -> Callable[[StoveState], float | None]:
    return lambda state: state.values.get(key)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JollyMec4HeatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[JollyMecSensor] = [
        JollyMecSensor(coordinator, description) for description in CORE_SENSORS
    ]
    for spec in coordinator.device_map.registers:
        if spec.unit == "Nr" and spec.name.lower().startswith("potenza"):
            entities.append(
                JollyMecSensor(
                    coordinator,
                    JollyMecSensorDescription(
                        key=spec.key,
                        name=spec.name,
                        state_class=SensorStateClass.MEASUREMENT,
                        value_fn=_value_getter(spec.key),
                    ),
                )
            )
    async_add_entities(entities)


class JollyMecSensor(JollyMec4HeatEntity, SensorEntity):
    entity_description: JollyMecSensorDescription

    def __init__(self, coordinator, description: JollyMecSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.coordinator.data)
