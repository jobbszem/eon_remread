#!/usr/bin/env python3

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from datetime import timedelta

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 3600  # 1 hour


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
):
    """Setup sensors from a config entry created in the integrations UI."""

    api = hass.data[DOMAIN][config_entry.entry_id]

    async def async_update_data():
        """Fetch data from API."""
        await api.update()
        return {
            "import": api.get_total_import(),
            "export": api.get_total_export(),
            "last_updated": api.get_last_updated(),
        }

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    entities = [
        GridEnergyImportSensor(coordinator, api),
        GridEnergyExportSensor(coordinator, api),
    ]

    async_add_entities(entities, update_before_add=False)


class GridEnergyImportSensor(CoordinatorEntity, SensorEntity):
    """Sensor for grid energy import (A+ - elhasznált)."""

    _attr_name = "Grid Energy Import"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt"
    _attr_unique_id = "eon_remread_energy_import"

    def __init__(self, coordinator, api):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.api = api

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("import", 0.0)
        return 0.0

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self.coordinator.data:
            last_updated = self.coordinator.data.get("last_updated")
            if last_updated:
                return {
                    "last_updated": last_updated.isoformat(),
                }
        return {}


class GridEnergyExportSensor(CoordinatorEntity, SensorEntity):
    """Sensor for grid energy export (A- - visszatermelt)."""

    _attr_name = "Grid Energy Export"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt-outline"
    _attr_unique_id = "eon_remread_energy_export"

    def __init__(self, coordinator, api):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.api = api

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("export", 0.0)
        return 0.0

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self.coordinator.data:
            last_updated = self.coordinator.data.get("last_updated")
            if last_updated:
                return {
                    "last_updated": last_updated.isoformat(),
                }
        return {}
