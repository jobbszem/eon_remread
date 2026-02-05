"""Config flow to configure EON Remote Read."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv

from .eon_remread import EonEnergyData

from . import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_POD

_LOGGER = logging.getLogger(__name__)


class EonRemreadConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle EON Remote Read config flow."""

    VERSION = 1

    def __init__(self) -> None:
        pass

    async def async_step_user(self, user_input=None):
        """Invoked when a user initiates a flow via the user interface."""

        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            pod = user_input.get(CONF_POD, "")
            
            # Teszteljük a bejelentkezést
            api = EonEnergyData(username, password, pod)
            success = await api.login()
            
            if success:
                return self.async_create_entry(
                    title=f"EON Remote Read ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_POD: pod,
                    }
                )
            else:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_POD, default=""): cv.string,
            }),
            errors=errors
        )
