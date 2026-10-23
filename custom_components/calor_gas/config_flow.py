# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Validate credentials in Home Assistant's password-masked setup form."""

from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .calor_portal import AuthenticationError, CalorPortal, PortalError
from .const import CONF_ACCOUNT_ID, DOMAIN

LOGGER = logging.getLogger(__name__)


class CalorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return await self._credentials("user", user_input)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._credentials("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._credentials("reconfigure", user_input)

    async def _credentials(self, step_id, user_input):
        errors = {}
        description_placeholders = {"detail": ""}
        if user_input is not None:
            session = async_create_clientsession(
                self.hass, auto_cleanup=False, cookie_jar=aiohttp.CookieJar(),
                timeout=aiohttp.ClientTimeout(total=20),
            )
            try:
                username = user_input[CONF_USERNAME].strip()
                password = user_input[CONF_PASSWORD]
                if not username or not password:
                    errors["base"] = "invalid_auth"
                else:
                    data = await CalorPortal(session, username, password).fetch()
                    await self.async_set_unique_id(data["account_id"])
                    entry_data = {CONF_USERNAME: username, CONF_PASSWORD: password,
                                  CONF_ACCOUNT_ID: data["account_id"]}
                    if step_id == "reauth_confirm":
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            self._get_reauth_entry(), data_updates=entry_data
                        )
                    if step_id == "reconfigure":
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(), data_updates=entry_data
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Calor Gas", data=entry_data)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except PortalError as err:
                errors["base"] = "portal_changed"
                # These are fixed parser messages or HTTP status numbers only;
                # never include response bodies, credentials or URLs with data.
                description_placeholders["detail"] = str(err)
                LOGGER.warning("Calor setup could not read the portal: %s", err)
            finally:
                # HA shares the TCP connector; detach our own session, do not
                # close that shared connector or other integrations' sessions.
                session.detach()

        schema = vol.Schema({
            vol.Required(CONF_USERNAME): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
            vol.Required(CONF_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        })
        return self.async_show_form(
            step_id=step_id, data_schema=schema, errors=errors,
            description_placeholders=description_placeholders,
        )
