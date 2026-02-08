#!/usr/bin/env python3

"""
EON Remote Read - Home Assistant integration
"""

import logging

from homeassistant.components.sensor import (  # type: ignore
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy  # type: ignore
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # type: ignore

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
):
    """Setup sensors from a config entry created in the integrations UI."""

    api = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        GridEnergyImportSensor(api),
        GridEnergyExportSensor(api),
    ]

    async_add_entities(entities, update_before_add=False)


class GridEnergyImportSensor(SensorEntity):
    """Sensor for grid energy import (A+ - consumed)."""

    _attr_name = "Grid Energy Import"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt"
    _attr_unique_id = "eon_remread_energy_import"
    _attr_should_poll = False

    def __init__(self, api):
        """Initialize the sensor."""
        self.api = api
        self._attr_native_value = 0.0

    async def async_added_to_hass(self):
        """Register update callback when sensor is added."""
        await super().async_added_to_hass()
        self.api.add_update_listener(self._on_api_update)
        # Set initial value
        self._attr_native_value = self.api.get_total_import()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Unregister update callback when sensor is removed."""
        await super().async_will_remove_from_hass()
        self.api.remove_update_listener(self._on_api_update)

    def _on_api_update(self):
        """Handle API data update."""
        self._attr_native_value = self.api.get_total_import()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        last_updated = self.api.get_last_updated()
        if last_updated:
            return {
                "last_updated": last_updated.isoformat(),
            }
        return {}


class GridEnergyExportSensor(SensorEntity):
    """Sensor for grid energy export (A- - exported)."""

    _attr_name = "Grid Energy Export"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt-outline"
    _attr_unique_id = "eon_remread_energy_export"
    _attr_should_poll = False

    def __init__(self, api):
        """Initialize the sensor."""
        self.api = api
        self._attr_native_value = 0.0

    async def async_added_to_hass(self):
        """Register update callback when sensor is added."""
        await super().async_added_to_hass()
        self.api.add_update_listener(self._on_api_update)
        # Set initial value
        self._attr_native_value = self.api.get_total_export()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Unregister update callback when sensor is removed."""
        await super().async_will_remove_from_hass()
        self.api.remove_update_listener(self._on_api_update)

    def _on_api_update(self):
        """Handle API data update."""
        self._attr_native_value = self.api.get_total_export()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        last_updated = self.api.get_last_updated()
        if last_updated:
            return {
                "last_updated": last_updated.isoformat(),
            }
        return {}
