#!/usr/bin/env python3

"""
EON Remote Read / EON Távleolvasás - Home Assistant integráció
"""

import logging
from datetime import datetime

from homeassistant.components.sensor import ( # type: ignore
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy # type: ignore
from homeassistant.core import HomeAssistant # type: ignore
from homeassistant.helpers.entity_platform import AddEntitiesCallback # type: ignore
from homeassistant.helpers.event import async_track_time_change # type: ignore
from homeassistant.helpers.update_coordinator import ( # type: ignore
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Update at these hours (0–23), minute 0. w1000 pattern: 6, 7, 9 + current hour at load
UPDATE_HOURS = [6, 7, 9]


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
        update_interval=None,  # Időpont-alapú frissítés (async_track_time_change)
    )

    # Update hours: 6, 7, 9 + the current hour at load (if not already present)
    hours = list(UPDATE_HOURS)
    now = datetime.now()
    if now.hour not in hours:
        hours.append(now.hour)
        hours.sort()

    async def _refresh_at_schedule(_now):
        await coordinator.async_request_refresh()

    # Time-based updates: every day at the specified hours, minute 0, second 0
    async_track_time_change(
        hass,
        _refresh_at_schedule,
        hour=hours,
        minute=0,
        second=0,
    )

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    entities = [
        GridEnergyImportSensor(coordinator, api),
        GridEnergyExportSensor(coordinator, api),
    ]

    async_add_entities(entities, update_before_add=False)


class GridEnergyImportSensor(CoordinatorEntity, SensorEntity):
    """Sensor for grid energy import (A+ - consumed)."""

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
    """Sensor for grid energy export (A- - exported)."""

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
