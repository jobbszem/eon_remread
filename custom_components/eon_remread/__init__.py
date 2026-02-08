#!/usr/bin/env python3

import logging
from datetime import datetime
from .eon_remread import EonEnergyData
from homeassistant.helpers.event import async_track_utc_time_change
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "eon_remread"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_POD = "pod"

# Update hours: 6, 7, 9 + current hour at initialization
UPDATE_HOURS = [6, 7, 9]


async def async_setup_entry(hass, entry):
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    pod = entry.data.get(CONF_POD, "")

    api = EonEnergyData(username, password, pod, hass)

    # Test authentication
    success = await api.login()

    if success:
        hass.data[DOMAIN][entry.entry_id] = api

        # Setup scheduled updates
        now = dt_util.utcnow()
        hours = list(UPDATE_HOURS)
        if now.hour not in hours:
            hours.append(now.hour)
            hours.sort()

        async def _update_at_schedule(_now):
            """Update data at scheduled hours."""
            await api.update()

        async_track_utc_time_change(
            hass,
            _update_at_schedule,
            hour=hours,
            minute=0,
            second=0,
        )

        # Initial data fetch
        _LOGGER.debug("Performing initial data fetch")
        await api.update()

        await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

        return True
    else:
        _LOGGER.error("Failed to authenticate with EON API")
        return False


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, ["sensor"]
        )
    except (OSError, RuntimeError) as e:
        _LOGGER.error("Error unloading platforms: %s", e)
        unload_ok = False
    finally:
        # Always close the API session, regardless of unload result
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            api = hass.data[DOMAIN].pop(entry.entry_id)
            try:
                await api.close()
            except (OSError, RuntimeError) as e:
                _LOGGER.error("Error closing API session: %s", e)

    return unload_ok
