# Copyright 2026 vodhash
"""Config flow for Jolly Mec 4HEAT."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthError, JollyMec4HeatApi, JollyMec4HeatError
from .const import CONF_DEVICE_ID, CONF_PIN, DEFAULT_PIN, DOMAIN
from .protocol import parse_device_map

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_PIN, default=DEFAULT_PIN): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class JollyMec4HeatConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()
            api = JollyMec4HeatApi(
                async_get_clientsession(self.hass),
                device_id,
                user_input[CONF_PIN].strip(),
                user_input[CONF_EMAIL].strip(),
                user_input[CONF_PASSWORD],
            )
            try:
                summary = await api.async_validate()
                device_map = parse_device_map(await api.async_get_filemap())
            except AuthError:
                errors["base"] = "invalid_auth"
            except JollyMec4HeatError:
                errors["base"] = "cannot_connect"
            else:
                if not device_map.is_supported:
                    errors["base"] = "unsupported_protocol"
                else:
                    return self.async_create_entry(
                        title=summary.get("Name") or device_id,
                        data={
                            CONF_DEVICE_ID: device_id,
                            CONF_PIN: user_input[CONF_PIN].strip(),
                            CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
