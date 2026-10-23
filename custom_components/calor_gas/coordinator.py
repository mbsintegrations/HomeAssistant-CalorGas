# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Collect and persist one shared last-known-good snapshot for all sensors."""

from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .cache import decode_snapshot, encode_snapshot
from .calor_portal import AuthenticationError, CalorPortal, PortalError
from .const import CONF_ACCOUNT_ID, DOMAIN, UPDATE_HOURS

LOGGER = logging.getLogger(__name__)


class CalorCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(hass, LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=timedelta(hours=UPDATE_HOURS))
        self.account_id = entry.data[CONF_ACCOUNT_ID]
        self.entry = entry
        self._store = Store(hass, 1, f"calor_gas_snapshot_{entry.entry_id}",
                            private=True, atomic_writes=True)
        self._cached_data = None
        self.data_stale = True
        self.portal_available = False
        self.last_refresh_error = None
        # Independent cookies; Home Assistant cleans this session up on unload.
        session = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar(), timeout=aiohttp.ClientTimeout(total=20)
        )
        self.portal = CalorPortal(session, entry.data["username"], entry.data["password"])

    async def async_load_cached_data(self):
        """Restore only the validated snapshot owned by this entry's account."""
        try:
            raw = await self._store.async_load()
            self._cached_data = decode_snapshot(raw, self.account_id)
        except (OSError, ValueError, TypeError):
            self._cached_data = None
            LOGGER.warning("Calor's saved snapshot could not be restored")

    async def _save_snapshot(self, raw):
        try:
            await self._store.async_save(raw)
        except OSError:
            LOGGER.warning("Calor's latest reading could not be persisted")

    def _retain_snapshot(self, message):
        self.portal_available = False
        self.last_refresh_error = message
        if self._cached_data is None:
            raise UpdateFailed(message)
        if not self.data_stale:
            LOGGER.warning("Calor's refresh failed; retaining the last successful reading: %s", message)
        self.data_stale = True
        return dict(self._cached_data)

    async def _async_update_data(self):
        try:
            data = await self.portal.fetch()
            if data["account_id"] != self.account_id:
                raise PortalError("Calor returned a different account; the reading was rejected")
            data["last_successful_sync"] = dt_util.utcnow()
            try:
                raw = encode_snapshot(data)
            except (ValueError, TypeError, KeyError, AttributeError) as err:
                raise PortalError("Calor returned an invalid snapshot; the reading was rejected") from err
            self._cached_data = dict(data)
            self.data_stale = False
            self.portal_available = True
            self.last_refresh_error = None
            await self._save_snapshot(raw)
            return data
        except AuthenticationError as err:
            if self._cached_data is None:
                raise ConfigEntryAuthFailed("Re-enter the Calor login credentials") from err
            self.entry.async_start_reauth(self.hass)
            return self._retain_snapshot("Re-enter the Calor login credentials")
        except PortalError as err:
            return self._retain_snapshot(str(err))
        except (aiohttp.ClientError, TimeoutError):
            return self._retain_snapshot("Could not reach the Calor portal")
