#!/usr/bin/env python3

import logging
from .eon_remread import EonEnergyData

_LOGGER = logging.getLogger(__name__)

DOMAIN = "eon_remread"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_POD = "pod"


async def async_setup_entry(hass, entry):
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    pod = entry.data.get(CONF_POD, "")

    api = EonEnergyData(username, password, pod, hass)

    # Teszteljük a bejelentkezést
    success = await api.login()
    
    if success:
        hass.data[DOMAIN][entry.entry_id] = api

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
        )

        return True
    else:
        _LOGGER.error("Failed to authenticate with EON API")
        return False
