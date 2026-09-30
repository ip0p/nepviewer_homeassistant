"""Config flow for NEPViewer Solar."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    NepviewerApiClient,
    NepviewerAuthenticationError,
    NepviewerConnectionError,
    NepviewerError,
)
from .const import CONF_ACCOUNT, DOMAIN

STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    client = NepviewerApiClient(
        async_get_clientsession(hass),
        account=data[CONF_ACCOUNT],
        password=data[CONF_PASSWORD],
    )
    await client.async_login()
    await client.async_get_sites()


class NepviewerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the NEPViewer configuration flow."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_ACCOUNT] = user_input[CONF_ACCOUNT].strip().lower()
            try:
                await _validate_input(self.hass, user_input)
            except NepviewerAuthenticationError:
                errors["base"] = "invalid_auth"
            except NepviewerConnectionError:
                errors["base"] = "cannot_connect"
            except NepviewerError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_ACCOUNT])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_ACCOUNT], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication for an expired legacy token."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect credentials and update the existing entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_ACCOUNT] = user_input[CONF_ACCOUNT].strip().lower()
            try:
                await _validate_input(self.hass, user_input)
            except NepviewerAuthenticationError:
                errors["base"] = "invalid_auth"
            except NepviewerConnectionError:
                errors["base"] = "cannot_connect"
            except NepviewerError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data=user_input,
                    unique_id=user_input[CONF_ACCOUNT],
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_SCHEMA, errors=errors
        )
