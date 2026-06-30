"""Number platform exposing the airflow set-point (m³/h) for each ventilation speed."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Coroutine
from dataclasses import dataclass
from typing import Any, Callable, cast

from aiocomfoconnect.const import VentilationSpeed
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)


@dataclass
class ComfoconnectNumberDescriptionMixin:
    """Mixin for required keys."""

    get_value_fn: Callable[[ComfoConnectBridge], Awaitable[Any]]
    set_value_fn: Callable[[ComfoConnectBridge, float], Awaitable[Any]]


@dataclass
class ComfoconnectNumberEntityDescription(NumberEntityDescription, ComfoconnectNumberDescriptionMixin):
    """Describes a ComfoConnect number entity."""


def _flow_description(speed: str, name: str) -> ComfoconnectNumberEntityDescription:
    """Build an airflow set-point number description for a ventilation speed."""
    return ComfoconnectNumberEntityDescription(
        key=f"flow_{speed}",
        name=name,
        icon="mdi:fan",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        native_min_value=0,
        native_max_value=400,
        native_step=1,
        get_value_fn=lambda ccb, speed=speed: cast(Coroutine, ccb.get_flow_for_speed(speed)),
        set_value_fn=lambda ccb, value, speed=speed: cast(Coroutine, ccb.set_flow_for_speed(speed, int(value))),
    )


NUMBER_TYPES = (
    _flow_description(VentilationSpeed.AWAY, "Airflow set-point (away)"),
    _flow_description(VentilationSpeed.LOW, "Airflow set-point (low)"),
    _flow_description(VentilationSpeed.MEDIUM, "Airflow set-point (medium)"),
    _flow_description(VentilationSpeed.HIGH, "Airflow set-point (high)"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ComfoConnect numbers."""
    ccb = hass.data[DOMAIN][config_entry.entry_id]

    numbers = [ComfoConnectNumber(ccb=ccb, config_entry=config_entry, description=description) for description in NUMBER_TYPES]

    async_add_entities(numbers, True)


class ComfoConnectNumber(NumberEntity):
    """Representation of a ComfoConnect number (airflow set-point)."""

    _attr_has_entity_name = True
    entity_description: ComfoconnectNumberEntityDescription

    def __init__(
        self,
        ccb: ComfoConnectBridge,
        config_entry: ConfigEntry,
        description: ComfoconnectNumberEntityDescription,
    ) -> None:
        """Initialize the ComfoConnect number."""
        self._ccb = ccb
        self.entity_description = description
        self._attr_unique_id = f"{self._ccb.uuid}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ccb.uuid)},
        )

    async def async_update(self) -> None:
        """Update the state."""
        self._attr_native_value = await self.entity_description.get_value_fn(self._ccb)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new airflow set-point."""
        await self.entity_description.set_value_fn(self._ccb, value)
        self._attr_native_value = value
        self.schedule_update_ha_state()
