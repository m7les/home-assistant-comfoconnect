"""Sensor for the ComfoConnect integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from aiocomfoconnect.sensors import (
    SENSOR_AIRFLOW_CONSTRAINTS,
    SENSOR_ANALOG_INPUT_1,
    SENSOR_ANALOG_INPUT_2,
    SENSOR_ANALOG_INPUT_3,
    SENSOR_ANALOG_INPUT_4,
    SENSOR_AVOIDED_COOLING,
    SENSOR_AVOIDED_COOLING_TOTAL,
    SENSOR_AVOIDED_COOLING_TOTAL_YEAR,
    SENSOR_AVOIDED_HEATING,
    SENSOR_AVOIDED_HEATING_TOTAL,
    SENSOR_AVOIDED_HEATING_TOTAL_YEAR,
    SENSOR_BYPASS_STATE,
    SENSOR_COMFOCOOL_CONDENSOR_TEMP,
    SENSOR_COMFOFOND_GHE_STATE,
    SENSOR_COMFOFOND_TEMP_GROUND,
    SENSOR_COMFOFOND_TEMP_OUTDOOR,
    SENSOR_COMFORTCONTROL_MODE,
    SENSOR_DAYS_TO_REPLACE_FILTER,
    SENSOR_FAN_EXHAUST_DUTY,
    SENSOR_FAN_EXHAUST_FLOW,
    SENSOR_FAN_EXHAUST_SPEED,
    SENSOR_FAN_SPEED_MODE_MODULATED,
    SENSOR_FAN_SUPPLY_DUTY,
    SENSOR_FAN_SUPPLY_FLOW,
    SENSOR_FAN_SUPPLY_SPEED,
    SENSOR_HUMIDITY_AFTER_PREHEATER,
    SENSOR_HUMIDITY_EXHAUST,
    SENSOR_HUMIDITY_EXTRACT,
    SENSOR_HUMIDITY_OUTDOOR,
    SENSOR_HUMIDITY_SUPPLY,
    SENSOR_NEXT_CHANGE_BYPASS,
    SENSOR_NEXT_CHANGE_FAN,
    SENSOR_OPERATING_MODE_2,
    SENSOR_POWER_USAGE,
    SENSOR_POWER_USAGE_TOTAL,
    SENSOR_POWER_USAGE_TOTAL_YEAR,
    SENSOR_PREHEATER_POWER,
    SENSOR_PREHEATER_POWER_TOTAL,
    SENSOR_PREHEATER_POWER_TOTAL_YEAR,
    SENSOR_RMOT,
    SENSOR_TARGET_TEMPERATURE,
    SENSOR_TEMPERATURE_EXHAUST,
    SENSOR_TEMPERATURE_EXTRACT,
    SENSOR_TEMPERATURE_OUTDOOR,
    SENSOR_TEMPERATURE_OUTDOOR_PREHEATED,
    SENSOR_TEMPERATURE_OUTDOOR_PREHEATED_2,
    SENSOR_TEMPERATURE_SUPPLY,
    SENSOR_TEMPERATURE_SUPPLY_PREHEATED,
    SENSORS,
    SENSORS_DEBUG,
)
from aiocomfoconnect.sensors import (
    Sensor as AioComfoConnectSensor,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

# Human-readable mappings for "mode" PDOs. The library deliberately returns raw
# integers; labelling lives here. Transcribed from the ESPHome project.
OPERATING_MODE_MAP = {
    -1: "auto",
    1: "manual_limited",
    2: "preset_rf",
    3: "preset_analog",
    4: "preset_rf_analog",
    5: "manual_permanent",
    6: "boost",
    7: "boost_rf",
    8: "bathroom_switch",
    11: "away",
    255: "auto",
}
OPERATING_MODE_OPTIONS = [
    "auto",
    "manual_limited",
    "manual_permanent",
    "boost",
    "boost_rf",
    "preset_rf",
    "preset_analog",
    "preset_rf_analog",
    "bathroom_switch",
    "away",
]

VENTILATION_MODE_MAP = {
    0: "disabled",
    1: "active",
    2: "overruling",
}
VENTILATION_MODE_OPTIONS = ["disabled", "active", "overruling"]


@dataclass
class ComfoconnectRequiredKeysMixin:
    """Mixin for required keys."""

    ccb_sensor: AioComfoConnectSensor


@dataclass
class ComfoconnectSensorEntityDescription(SensorEntityDescription, ComfoconnectRequiredKeysMixin):
    """Describes ComfoConnect sensor entity."""

    throttle: bool = False
    mapping: Callable = None


SENSOR_TYPES = (
    ComfoconnectSensorEntityDescription(
        key=SENSOR_TEMPERATURE_EXTRACT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Inside temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_TEMPERATURE_EXTRACT),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_HUMIDITY_EXTRACT,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Inside humidity",
        native_unit_of_measurement=PERCENTAGE,
        ccb_sensor=SENSORS.get(SENSOR_HUMIDITY_EXTRACT),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_RMOT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Current RMOT",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_RMOT),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_TEMPERATURE_OUTDOOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Outside temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_TEMPERATURE_OUTDOOR),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_HUMIDITY_OUTDOOR,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Outside humidity",
        native_unit_of_measurement=PERCENTAGE,
        ccb_sensor=SENSORS.get(SENSOR_HUMIDITY_OUTDOOR),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_TEMPERATURE_SUPPLY,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_TEMPERATURE_SUPPLY),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_HUMIDITY_SUPPLY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply humidity",
        native_unit_of_measurement=PERCENTAGE,
        ccb_sensor=SENSORS.get(SENSOR_HUMIDITY_SUPPLY),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_FAN_SUPPLY_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply fan speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan-plus",
        ccb_sensor=SENSORS.get(SENSOR_FAN_SUPPLY_SPEED),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_FAN_SUPPLY_DUTY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply fan duty",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fan-plus",
        ccb_sensor=SENSORS.get(SENSOR_FAN_SUPPLY_DUTY),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_FAN_EXHAUST_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust fan speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        icon="mdi:fan-minus",
        ccb_sensor=SENSORS.get(SENSOR_FAN_EXHAUST_SPEED),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_FAN_EXHAUST_DUTY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust fan duty",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:fan-minus",
        ccb_sensor=SENSORS.get(SENSOR_FAN_EXHAUST_DUTY),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_TEMPERATURE_EXHAUST,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_TEMPERATURE_EXHAUST),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_HUMIDITY_EXHAUST,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust humidity",
        native_unit_of_measurement=PERCENTAGE,
        ccb_sensor=SENSORS.get(SENSOR_HUMIDITY_EXHAUST),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_FAN_SUPPLY_FLOW,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply airflow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:fan-plus",
        ccb_sensor=SENSORS.get(SENSOR_FAN_SUPPLY_FLOW),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_FAN_EXHAUST_FLOW,
        state_class=SensorStateClass.MEASUREMENT,
        name="Exhaust airflow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:fan-minus",
        ccb_sensor=SENSORS.get(SENSOR_FAN_EXHAUST_FLOW),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_BYPASS_STATE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Bypass state",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:camera-iris",
        ccb_sensor=SENSORS.get(SENSOR_BYPASS_STATE),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_DAYS_TO_REPLACE_FILTER,
        name="Days to replace filter",
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:calendar",
        ccb_sensor=SENSORS.get(SENSOR_DAYS_TO_REPLACE_FILTER),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_POWER_USAGE,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        name="Ventilation current power usage",
        native_unit_of_measurement=UnitOfPower.WATT,
        ccb_sensor=SENSORS.get(SENSOR_POWER_USAGE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_POWER_USAGE_TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Ventilation total energy usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ccb_sensor=SENSORS.get(SENSOR_POWER_USAGE_TOTAL),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_PREHEATER_POWER,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        name="Preheater current power usage",
        native_unit_of_measurement=UnitOfPower.WATT,
        ccb_sensor=SENSORS.get(SENSOR_PREHEATER_POWER),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_PREHEATER_POWER_TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Preheater total energy usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ccb_sensor=SENSORS.get(SENSOR_PREHEATER_POWER_TOTAL),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_ANALOG_INPUT_1,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Analog Input 1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        ccb_sensor=SENSORS.get(SENSOR_ANALOG_INPUT_1),
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_ANALOG_INPUT_2,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Analog Input 2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        ccb_sensor=SENSORS.get(SENSOR_ANALOG_INPUT_2),
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_ANALOG_INPUT_3,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Analog Input 3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        ccb_sensor=SENSORS.get(SENSOR_ANALOG_INPUT_3),
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_ANALOG_INPUT_4,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Analog Input 4",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        ccb_sensor=SENSORS.get(SENSOR_ANALOG_INPUT_4),
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_AIRFLOW_CONSTRAINTS,
        icon="mdi:fan-alert",
        name="Airflow Constraint",
        ccb_sensor=SENSORS.get(SENSOR_AIRFLOW_CONSTRAINTS),
        entity_category=EntityCategory.DIAGNOSTIC,
        mapping=lambda x: x[0] if x else "",
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_COMFOFOND_GHE_STATE,
        state_class=SensorStateClass.MEASUREMENT,
        name="ComfoFond GHE state",
        native_unit_of_measurement=PERCENTAGE,
        ccb_sensor=SENSORS.get(SENSOR_COMFOFOND_GHE_STATE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_COMFOFOND_TEMP_GROUND,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="ComfoFond ground temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_COMFOFOND_TEMP_GROUND),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_COMFOFOND_TEMP_OUTDOOR,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="ComfoFond outdoor air temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_COMFOFOND_TEMP_OUTDOOR),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_COMFOCOOL_CONDENSOR_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="ComfoCool condensor temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_COMFOCOOL_CONDENSOR_TEMP),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Energy / avoided heating & cooling ---
    ComfoconnectSensorEntityDescription(
        key=SENSOR_POWER_USAGE_TOTAL_YEAR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Ventilation energy usage (year)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ccb_sensor=SENSORS.get(SENSOR_POWER_USAGE_TOTAL_YEAR),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_PREHEATER_POWER_TOTAL_YEAR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Preheater energy usage (year)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ccb_sensor=SENSORS.get(SENSOR_PREHEATER_POWER_TOTAL_YEAR),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_AVOIDED_HEATING,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        name="Avoided heating power",
        native_unit_of_measurement=UnitOfPower.WATT,
        ccb_sensor=SENSORS.get(SENSOR_AVOIDED_HEATING),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_AVOIDED_HEATING_TOTAL_YEAR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Avoided heating energy (year)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ccb_sensor=SENSORS.get(SENSOR_AVOIDED_HEATING_TOTAL_YEAR),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_AVOIDED_HEATING_TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Avoided heating energy (total)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ccb_sensor=SENSORS.get(SENSOR_AVOIDED_HEATING_TOTAL),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_AVOIDED_COOLING,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        name="Avoided cooling power",
        native_unit_of_measurement=UnitOfPower.WATT,
        ccb_sensor=SENSORS.get(SENSOR_AVOIDED_COOLING),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_AVOIDED_COOLING_TOTAL_YEAR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Avoided cooling energy (year)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ccb_sensor=SENSORS.get(SENSOR_AVOIDED_COOLING_TOTAL_YEAR),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_AVOIDED_COOLING_TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        name="Avoided cooling energy (total)",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ccb_sensor=SENSORS.get(SENSOR_AVOIDED_COOLING_TOTAL),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    # --- Temperatures / humidity (preheated / post-heated) ---
    ComfoconnectSensorEntityDescription(
        key=SENSOR_TARGET_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Profile target temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_TARGET_TEMPERATURE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_TEMPERATURE_OUTDOOR_PREHEATED,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Outdoor temperature (preheated)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_TEMPERATURE_OUTDOOR_PREHEATED),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_TEMPERATURE_OUTDOOR_PREHEATED_2,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Outdoor temperature (preheated, alt)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_TEMPERATURE_OUTDOOR_PREHEATED_2),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_TEMPERATURE_SUPPLY_PREHEATED,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Supply temperature (preheated)",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ccb_sensor=SENSORS.get(SENSOR_TEMPERATURE_SUPPLY_PREHEATED),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_HUMIDITY_AFTER_PREHEATER,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        name="Outdoor humidity (after preheater)",
        native_unit_of_measurement=PERCENTAGE,
        ccb_sensor=SENSORS.get(SENSOR_HUMIDITY_AFTER_PREHEATER),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # --- Operation ---
    ComfoconnectSensorEntityDescription(
        key=SENSOR_FAN_SPEED_MODE_MODULATED,
        state_class=SensorStateClass.MEASUREMENT,
        name="Fan speed (modulated)",
        icon="mdi:fan",
        ccb_sensor=SENSORS.get(SENSOR_FAN_SPEED_MODE_MODULATED),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_NEXT_CHANGE_FAN,
        device_class=SensorDeviceClass.DURATION,
        name="Fan speed next change",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        ccb_sensor=SENSORS.get(SENSOR_NEXT_CHANGE_FAN),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        mapping=lambda x: x if 0 <= x < 0xFFFFFFFF else None,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_NEXT_CHANGE_BYPASS,
        device_class=SensorDeviceClass.DURATION,
        name="Bypass next change",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-outline",
        ccb_sensor=SENSORS.get(SENSOR_NEXT_CHANGE_BYPASS),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        mapping=lambda x: x if 0 <= x < 0xFFFFFFFF else None,
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_OPERATING_MODE_2,
        device_class=SensorDeviceClass.ENUM,
        name="Operating mode",
        translation_key="operating_mode",
        options=OPERATING_MODE_OPTIONS,
        icon="mdi:fan-auto",
        ccb_sensor=SENSORS.get(SENSOR_OPERATING_MODE_2),
        # Primary state surface (ESPHome-style): auto / boost / boost_rf /
        # bathroom_switch / away / manual_*. Automate directly on this.
        # Values stay snake_case (stable); UI labels come from translations.
        mapping=lambda x: OPERATING_MODE_MAP.get(x),
    ),
    ComfoconnectSensorEntityDescription(
        key=SENSOR_COMFORTCONTROL_MODE,
        device_class=SensorDeviceClass.ENUM,
        name="Sensor ventilation mode",
        translation_key="ventilation_mode",
        options=VENTILATION_MODE_OPTIONS,
        icon="mdi:fan-auto",
        ccb_sensor=SENSORS.get(SENSOR_COMFORTCONTROL_MODE),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        mapping=lambda x: VENTILATION_MODE_MAP.get(x),
    ),
)

# Disabled-by-default diagnostic entities for every PDO whose meaning is not yet
# documented in the library (named "sensor_<id>"). These let advanced users probe
# the unit; they are off by default to avoid clutter.
DEBUG_SENSOR_TYPES = tuple(
    ComfoconnectSensorEntityDescription(
        key=sensor_id,
        name=f"PDO {sensor_id}",
        ccb_sensor=SENSORS.get(sensor_id),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        throttle=True,
    )
    for sensor_id in sorted(SENSORS_DEBUG)
)


@dataclass
class ComfoconnectPropertySensorEntityDescription(SensorEntityDescription):
    """Describes a polled RMI-property ComfoConnect sensor.

    Unlike the PDO sensors above (which are pushed over the dispatcher), these read
    a static installer/configuration value from the unit via a library getter.
    """

    get_value_fn: Callable = None


# Text maps for enum-ish config properties (library returns raw ints).
_ALTITUDE_BANDS = {0: "0-500 m", 1: "500-1000 m", 2: "1000-1500 m", 3: "1500-2000 m"}
_CONTROL_MODES = {0: "flow control", 1: "constant flow"}
_BATHROOM_MODES = {0: "fixed", 1: "mirrored"}


async def _altitude_band(ccb):
    return _ALTITUDE_BANDS.get(await ccb.get_altitude(), None)


async def _control_mode(ccb):
    return _CONTROL_MODES.get(await ccb.get_ventilation_control_mode(), None)


async def _bathroom_mode(ccb):
    return _BATHROOM_MODES.get(await ccb.get_bathroom_switch_mode(), None)


# Read-only diagnostics polled over RMI (node info + installer configuration). None
# of these stream as PDOs, so they live on their own polled entity. All are disabled
# by default to keep the entity list clean; enable the ones you care about.
PROPERTY_SENSOR_TYPES = (
    # --- Node identity ---
    ComfoconnectPropertySensorEntityDescription(
        key="serial_number",
        name="Serial number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_serial_number(),
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="model",
        name="Model",
        icon="mdi:hvac",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_model(),
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="firmware_version",
        name="Firmware version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_firmware_version(),
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="article_number",
        name="Article number",
        icon="mdi:barcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_article_number(),
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="country",
        name="Country",
        icon="mdi:earth",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_country(),
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="unit_name",
        name="Unit name",
        icon="mdi:rename-box",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_name(),
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="orientation",
        name="Orientation",
        icon="mdi:arrow-decision",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_orientation(),
    ),
    # --- Installer / ventilation configuration ---
    ComfoconnectPropertySensorEntityDescription(
        key="altitude",
        name="Altitude band",
        icon="mdi:image-filter-hdr",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=_altitude_band,
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="ventilation_control_mode",
        name="Ventilation control mode",
        icon="mdi:fan-chevron-up",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=_control_mode,
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="unbalance",
        name="Unbalance",
        icon="mdi:scale-unbalanced",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_unbalance(),
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="rmot_setpoint_heating",
        name="RMOT setpoint (heating period)",
        icon="mdi:thermometer-chevron-down",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_rmot_setpoint("heating"),
    ),
    ComfoconnectPropertySensorEntityDescription(
        key="rmot_setpoint_cooling",
        name="RMOT setpoint (cooling period)",
        icon="mdi:thermometer-chevron-up",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=lambda ccb: ccb.get_rmot_setpoint("cooling"),
    ),
    # --- Bathroom switch (installer) ---
    # boost_duration (0x0c) and activation_delay (0x0b) are writable, so they live on
    # the number platform. Mode (0x0d) accepts a write but the unit ignores it (it
    # needs a second physical switch for "mirrored"), so it stays read-only here.
    ComfoconnectPropertySensorEntityDescription(
        key="bathroom_switch_mode",
        name="Bathroom switch mode",
        icon="mdi:toggle-switch-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        get_value_fn=_bathroom_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ComfoConnect sensors."""
    ccb = hass.data[DOMAIN][config_entry.entry_id]

    descriptions = (*SENSOR_TYPES, *DEBUG_SENSOR_TYPES)
    sensors = [ComfoConnectSensor(ccb=ccb, config_entry=config_entry, description=description) for description in descriptions]
    sensors += [ComfoConnectPropertySensor(ccb=ccb, config_entry=config_entry, description=description) for description in PROPERTY_SENSOR_TYPES]

    async_add_entities(sensors, True)


class ComfoConnectSensor(SensorEntity):
    """Representation of a ComfoConnect sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description: ComfoconnectSensorEntityDescription

    def __init__(
        self,
        ccb: ComfoConnectBridge,
        config_entry: ConfigEntry,
        description: ComfoconnectSensorEntityDescription,
    ) -> None:
        """Initialize the ComfoConnect sensor."""
        self._ccb = ccb
        self.entity_description = description
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

        # If the sensor should be throttled, pass it through the Throttle utility
        if self.entity_description.throttle:
            update_handler = Throttle(MIN_TIME_BETWEEN_UPDATES)(self._handle_update)
        else:
            update_handler = self._handle_update

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(self._ccb.uuid, self.entity_description.key),
                update_handler,
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
            self._attr_native_value = self.entity_description.mapping(value)
        else:
            self._attr_native_value = value
        self.schedule_update_ha_state()


class ComfoConnectPropertySensor(SensorEntity):
    """A polled sensor reading a static RMI property (e.g. installer settings)."""

    _attr_has_entity_name = True
    entity_description: ComfoconnectPropertySensorEntityDescription

    def __init__(
        self,
        ccb: ComfoConnectBridge,
        config_entry: ConfigEntry,
        description: ComfoconnectPropertySensorEntityDescription,
    ) -> None:
        """Initialize the property sensor."""
        self._ccb = ccb
        self.entity_description = description
        self._attr_unique_id = f"{self._ccb.uuid}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ccb.uuid)},
        )

    async def async_update(self) -> None:
        """Poll the property value; leave unavailable if the unit doesn't expose it."""
        try:
            self._attr_native_value = await self.entity_description.get_value_fn(self._ccb)
        except Exception as err:  # noqa: BLE001 - hardware-dependent; degrade gracefully
            _LOGGER.debug("Could not read property sensor %s: %s", self.entity_description.key, err)
            self._attr_native_value = None
