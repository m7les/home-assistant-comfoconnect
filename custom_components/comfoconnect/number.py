"""Number platform exposing the airflow set-point (m³/h) for each ventilation speed."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Coroutine
from dataclasses import dataclass
from typing import Any, Callable, cast

from aiocomfoconnect.const import VentilationSpeed
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberEntityDescription, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)

# Default durations (minutes) used before the user picks one / on first run.
BOOST_DURATION_DEFAULT = 30
BYPASS_DURATION_DEFAULT = 60


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
    # Installer bathroom-switch settings — writable, verified against real hardware.
    # Disabled by default: these are commissioning values, not everyday controls.
    ComfoconnectNumberEntityDescription(
        key="bathroom_switch_boost_duration",
        name="Bathroom switch boost duration",
        icon="mdi:timer-cog-outline",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=1,
        native_max_value=60,
        native_step=1,
        get_value_fn=lambda ccb: cast(Coroutine, ccb.get_bathroom_switch_boost_duration()),
        set_value_fn=lambda ccb, value: cast(Coroutine, ccb.set_bathroom_switch_boost_duration(int(value))),
    ),
    ComfoconnectNumberEntityDescription(
        key="bathroom_switch_activation_delay",
        name="Bathroom switch activation delay",
        icon="mdi:timer-sand",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=600,
        native_step=1,
        get_value_fn=lambda ccb: cast(Coroutine, ccb.get_bathroom_switch_activation_delay()),
        set_value_fn=lambda ccb, value: cast(Coroutine, ccb.set_bathroom_switch_activation_delay(int(value))),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ComfoConnect numbers."""
    ccb = hass.data[DOMAIN][config_entry.entry_id]

    numbers = [ComfoConnectNumber(ccb=ccb, config_entry=config_entry, description=description) for description in NUMBER_TYPES]
    numbers.append(ComfoConnectLocalDurationNumber(ccb, "boost_duration", "Boost duration", "boost_duration_minutes", BOOST_DURATION_DEFAULT))
    numbers.append(ComfoConnectLocalDurationNumber(ccb, "bypass_duration", "Bypass duration", "bypass_duration_minutes", BYPASS_DURATION_DEFAULT))

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


class ComfoConnectLocalDurationNumber(RestoreNumber):
    """A HA-local duration preference (minutes) shared with a companion control.

    Not a bridge setting: the app-boost and bypass overrides have no persisted
    duration on the unit, so we store the user's preferred length here and feed it
    to the companion (switch.boost / select.bypass_mode) when it activates. ``0``
    means "until cancelled" (the companion maps that to the protocol's indefinite
    ``-1`` timeout). The value is stashed on the shared bridge object under ``attr``
    so the companion can read it, and restored across restarts.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:timer-cog-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 1440
    _attr_native_step = 5
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, ccb: ComfoConnectBridge, key: str, name: str, attr: str, default: int) -> None:
        """Initialize a local duration-preference number."""
        self._ccb = ccb
        self._attr = attr
        self._attr_name = name
        self._attr_unique_id = f"{self._ccb.uuid}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ccb.uuid)},
        )
        self._attr_native_value = default
        # Seed the shared value so the companion has something before restore runs.
        setattr(self._ccb, attr, default)

    async def async_added_to_hass(self) -> None:
        """Restore the last chosen duration."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value
        setattr(self._ccb, self._attr, self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Store the new duration."""
        self._attr_native_value = value
        setattr(self._ccb, self._attr, value)
        self.schedule_update_ha_state()
