# Copyright 2026 vodhash
"""Shared base entity for Jolly Mec 4HEAT."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BASE
from .const import DOMAIN, MANUFACTURER
from .coordinator import JollyMec4HeatCoordinator


class JollyMec4HeatEntity(CoordinatorEntity[JollyMec4HeatCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: JollyMec4HeatCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            manufacturer=MANUFACTURER,
            name=coordinator.data.name or "Jolly Mec",
            model=coordinator.product_code or None,
            sw_version=coordinator.data.firmware or None,
            configuration_url=BASE,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.online
