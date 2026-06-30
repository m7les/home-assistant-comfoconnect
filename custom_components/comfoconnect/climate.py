"""Climate platform: a thermostat-style wrapper around the temperature profile (ported from ESPHome, disabled by default)."""

from __future__ import annotations

import logging
from typing import Any

from aiocomfoconnect.const import VentilationTemperatureProfile
from aiocomfoconnect.sensors import (
    SENSOR_PROFILE_TEMPERATURE,
    SENSOR_TEMPERATURE_EXTRACT,
    SENSORS,
)
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)

PRESET_MODES = [
    VentilationTemperatureProfile.WARM,
    VentilationTemperatureProfile.NORMAL,
    VentilationTemperatureProfile.COOL,
]

# PDO 67 (temperature profile) raw value -> profile
PROFILE_MAP = {
    0: VentilationTemperatureProfile.NORMAL,
    1: VentilationTemperatureProfile.COOL,
    2: VentilationTemperatureProfile.WARM,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ComfoConnect climate entity."""
    ccb = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([ComfoConnectClimate(ccb=ccb, config_entry=config_entry)], True)


class ComfoConnectClimate(ClimateEntity):
    """Thermostat-style wrapper around the ComfoConnect temperature profile."""

    _attr_has_entity_name = True
    _attr_name = "Climate"
    _attr_icon = "mdi:air-filter"
    _attr_should_poll = True
    _attr_entity_registry_enabled_default = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.FAN_ONLY]
    _attr_hvac_mode = HVACMode.FAN_ONLY
    _attr_preset_modes = list(PRESET_MODES)
    _attr_supported_features = ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 15
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5

    def __init__(self, ccb: ComfoConnectBridge, config_entry: ConfigEntry) -> None:
        """Initialize the ComfoConnect climate entity."""
        self._ccb = ccb
        self._attr_unique_id = f"{self._ccb.uuid}-climate"
        self._attr_preset_mode = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ccb.uuid)},
        )

    async def async_added_to_hass(self) -> None:
        """Register for current-temperature and profile updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(self._ccb.uuid, SENSOR_TEMPERATURE_EXTRACT),
                self._handle_temperature_update,
            )
        )
        await self._ccb.register_sensor(SENSORS.get(SENSOR_TEMPERATURE_EXTRACT))

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(self._ccb.uuid, SENSOR_PROFILE_TEMPERATURE),
                self._handle_profile_update,
            )
        )
        await self._ccb.register_sensor(SENSORS.get(SENSOR_PROFILE_TEMPERATURE))

    def _handle_temperature_update(self, value: float) -> None:
        """Handle current temperature updates."""
        self._attr_current_temperature = value
        self.schedule_update_ha_state()

    def _handle_profile_update(self, value: int) -> None:
        """Handle temperature-profile updates."""
        self._attr_preset_mode = PROFILE_MAP.get(value)
        self.schedule_update_ha_state()

    async def async_update(self) -> None:
        """Refresh the target temperature for the active profile."""
        profile = self._attr_preset_mode or await self._ccb.get_temperature_profile()
        self._attr_preset_mode = profile
        self._attr_target_temperature = await self._ccb.get_target_temperature(profile)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set a new temperature profile."""
        if preset_mode not in self.preset_modes:
            raise ValueError(f"Invalid preset mode: {preset_mode}")
        await self._ccb.set_temperature_profile(preset_mode)
        self._attr_preset_mode = preset_mode
        self.schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature for the active profile."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        profile = self._attr_preset_mode or await self._ccb.get_temperature_profile()
        await self._ccb.set_target_temperature(profile, temperature)
        self._attr_target_temperature = temperature
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """HVAC mode is fixed (ventilation is always on); nothing to do."""
