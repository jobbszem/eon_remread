"""Config flow to configure EON Remote Read."""
from __future__ import annotations

import logging

import voluptuous as vol # pyright: ignore[reportMissingImports]

from homeassistant import config_entries # pyright: ignore[reportMissingImports]
import homeassistant.helpers.config_validation as cv # pyright: ignore[reportMissingImports]

from .eon_remread import EonEnergyData

from . import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_POD

_LOGGER = logging.getLogger(__name__)


class EonRemreadConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle EON Remote Read config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""

    async def async_step_user(self, user_input=None):
        """Invoked when a user initiates a flow via the user interface."""

        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            pod = user_input.get(CONF_POD, "")

            # Test authentication
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

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of EON Remote Read."""
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            pod = user_input.get(CONF_POD, "")

            # Test the new authentication credentials
            api = EonEnergyData(username, password, pod)
            success = await api.login()

            if success:
                self.hass.config_entries.async_update_entry(
                    config_entry,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_POD: pod,
                    },
                    title=f"EON Remote Read ({username})",
                )
                return self.async_abort(reason="reconfigure_successful")
            else:
                errors["base"] = "invalid_auth"

        # Load current values
        current_data = config_entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_USERNAME, default=current_data.get(CONF_USERNAME)
                ): cv.string,
                vol.Required(
                    CONF_PASSWORD, default=current_data.get(CONF_PASSWORD)
                ): cv.string,
                vol.Optional(
                    CONF_POD, default=current_data.get(CONF_POD, "")
                ): cv.string,
            }),
            errors=errors,
        )
