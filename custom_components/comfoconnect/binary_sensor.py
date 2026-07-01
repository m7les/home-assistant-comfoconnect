"""Binary Sensor for the ComfoConnect integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from aiocomfoconnect.sensors import (
    SENSOR_CHANGING_FILTERS,
    SENSOR_COMFOCOOL_STATE,
    SENSOR_COMFOFOND_GHE_PRESENT,
    SENSOR_DEVICE_STATE,
    SENSOR_FROSTPROTECTION_UNBALANCE,
    SENSOR_OPERATING_MODE_2,
    SENSOR_RF_PAIRING_MODE,
    SENSOR_SEASON_COOLING_ACTIVE,
    SENSOR_SEASON_HEATING_ACTIVE,
    SENSORS,
)
from aiocomfoconnect.sensors import (
    Sensor as AioComfoConnectSensor,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)


@dataclass
class ComfoconnectRequiredKeysMixin:
    """Mixin for required keys."""

    ccb_sensor: AioComfoConnectSensor


@dataclass
class ComfoconnectBinarySensorEntityDescription(BinarySensorEntityDescription, ComfoconnectRequiredKeysMixin):
    """Describes ComfoConnect binary sensor entity."""

    # Optional callable to derive on/off from a raw PDO value. Defaults to bool(value).
    mapping: Callable[[int], bool] = None


SENSOR_TYPES = (
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_OPERATING_MODE_2,
        name="Boost active",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:fan-plus",
        ccb_sensor=SENSORS.get(SENSOR_OPERATING_MODE_2),
        # Operating mode: 6=boost, 7=boost_rf, 8=bathroom_switch (physical wall button).
        # On for any boost trigger; sensor.operating_mode tells you which source.
        mapping=lambda value: value in (6, 7, 8),
    ),
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_DEVICE_STATE,
        name="Away",
        icon="mdi:airplane",
        ccb_sensor=SENSORS.get(SENSOR_DEVICE_STATE),
        mapping=lambda value: value == 7,
    ),
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_CHANGING_FILTERS,
        name="Changing filters",
        device_class=BinarySensorDeviceClass.RUNNING,
        ccb_sensor=SENSORS.get(SENSOR_CHANGING_FILTERS),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        mapping=lambda value: value == 2,
    ),
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_RF_PAIRING_MODE,
        name="RF pairing active",
        ccb_sensor=SENSORS.get(SENSOR_RF_PAIRING_MODE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        mapping=lambda value: value == 1,
    ),
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_FROSTPROTECTION_UNBALANCE,
        name="Frost protection unbalance",
        device_class=BinarySensorDeviceClass.PROBLEM,
        ccb_sensor=SENSORS.get(SENSOR_FROSTPROTECTION_UNBALANCE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        mapping=lambda value: bool(value),
    ),
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_SEASON_HEATING_ACTIVE,
        name="Heating Season Active",
        ccb_sensor=SENSORS.get(SENSOR_SEASON_HEATING_ACTIVE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_SEASON_COOLING_ACTIVE,
        name="Cooling Season Active",
        ccb_sensor=SENSORS.get(SENSOR_SEASON_COOLING_ACTIVE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_COMFOFOND_GHE_PRESENT,
        name="ComfoFond GHE present",
        ccb_sensor=SENSORS.get(SENSOR_COMFOFOND_GHE_PRESENT),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectBinarySensorEntityDescription(
        key=SENSOR_COMFOCOOL_STATE,
        name="ComfoCool state",
        ccb_sensor=SENSORS.get(SENSOR_COMFOCOOL_STATE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ComfoConnect binary sensors."""
    ccb = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [ComfoConnectBinarySensor(ccb=ccb, config_entry=config_entry, description=description) for description in SENSOR_TYPES]

    async_add_entities(sensors, True)


class ComfoConnectBinarySensor(BinarySensorEntity):
    """Representation of a ComfoConnect sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description: ComfoconnectBinarySensorEntityDescription

    def __init__(
        self,
        ccb: ComfoConnectBridge,
        config_entry: ConfigEntry,
        description: ComfoconnectBinarySensorEntityDescription,
    ) -> None:
        """Initialize the ComfoConnect sensor."""
        self._ccb = ccb
        self.entity_description = description
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{self._ccb.uuid}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ccb.uuid)},
        )

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""
        _LOGGER.debug(
            "Registering for sensor %s (%d)",
            self.entity_description.name,
            self.entity_description.key,
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(self._ccb.uuid, self.entity_description.key),
                self._handle_update,
            )
        )
        await self._ccb.register_sensor(self.entity_description.ccb_sensor)

    def _handle_update(self, value):
        """Handle update callbacks."""
        _LOGGER.debug(
            "Handle update for sensor %s (%d): %s",
            self.entity_description.name,
            self.entity_description.key,
            value,
        )

        if self.entity_description.mapping:
            self._attr_is_on = self.entity_description.mapping(value)
        else:
            self._attr_is_on = bool(value)
        self.schedule_update_ha_state()
