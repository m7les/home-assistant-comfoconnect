"""Switch platform for the ComfoConnect integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Coroutine
from dataclasses import dataclass
from typing import Any, Callable, cast

from aiocomfoconnect.const import ComfoCoolMode
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)

# Fallback if the boost-duration number hasn't seeded the shared value yet.
BOOST_DURATION_DEFAULT = 30


def _boost_timeout(ccb: ComfoConnectBridge) -> int:
    """Resolve the boost timeout (seconds) from the boost-duration number.

    ``0`` (or unset) means "until cancelled", mapped to the protocol's indefinite
    ``-1`` timeout so the switch behaves as a latch rather than self-expiring.
    """
    minutes = getattr(ccb, "boost_duration_minutes", BOOST_DURATION_DEFAULT)
    if not minutes:
        return -1
    return int(minutes) * 60


@dataclass
class ComfoconnectSwitchDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[ComfoConnectBridge], Awaitable[bool]]
    turn_on_fn: Callable[[ComfoConnectBridge], Awaitable[Any]]
    turn_off_fn: Callable[[ComfoConnectBridge], Awaitable[Any]]


@dataclass
class ComfoconnectSwitchEntityDescription(SwitchEntityDescription, ComfoconnectSwitchDescriptionMixin):
    """Describes a ComfoConnect switch entity."""


SWITCH_TYPES = (
    ComfoconnectSwitchEntityDescription(
        key="away",
        name="Away",
        icon="mdi:airplane",
        is_on_fn=lambda ccb: cast(Coroutine, ccb.get_away()),
        turn_on_fn=lambda ccb: cast(Coroutine, ccb.set_away(True)),
        turn_off_fn=lambda ccb: cast(Coroutine, ccb.set_away(False)),
    ),
    ComfoconnectSwitchEntityDescription(
        key="boost",
        name="Boost",
        icon="mdi:fan-plus",
        is_on_fn=lambda ccb: cast(Coroutine, ccb.get_boost()),
        turn_on_fn=lambda ccb: cast(Coroutine, ccb.set_boost(True, _boost_timeout(ccb))),
        turn_off_fn=lambda ccb: cast(Coroutine, ccb.set_boost(False)),
    ),
    ComfoconnectSwitchEntityDescription(
        key="comfocool",
        name="ComfoCool",
        icon="mdi:snowflake",
        is_on_fn=lambda ccb: cast(Coroutine, ccb.get_comfocool_mode()),
        turn_on_fn=lambda ccb: cast(Coroutine, ccb.set_comfocool_mode(ComfoCoolMode.AUTO)),
        turn_off_fn=lambda ccb: cast(Coroutine, ccb.set_comfocool_mode(ComfoCoolMode.OFF)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ComfoConnect switches."""
    ccb = hass.data[DOMAIN][config_entry.entry_id]

    switches = [ComfoConnectSwitch(ccb=ccb, config_entry=config_entry, description=description) for description in SWITCH_TYPES]

    async_add_entities(switches, True)


class ComfoConnectSwitch(SwitchEntity):
    """Representation of a ComfoConnect switch."""

    _attr_has_entity_name = True
    entity_description: ComfoconnectSwitchEntityDescription

    def __init__(
        self,
        ccb: ComfoConnectBridge,
        config_entry: ConfigEntry,
        description: ComfoconnectSwitchEntityDescription,
    ) -> None:
        """Initialize the ComfoConnect switch."""
        self._ccb = ccb
        self.entity_description = description
        self._attr_unique_id = f"{self._ccb.uuid}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._ccb.uuid)},
        )

    async def async_update(self) -> None:
        """Update the state."""
        self._attr_is_on = await self.entity_description.is_on_fn(self._ccb)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.turn_on_fn(self._ccb)
        self._attr_is_on = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.turn_off_fn(self._ccb)
        self._attr_is_on = False
        self.schedule_update_ha_state()
