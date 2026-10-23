# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Read-only Calor Gas tank monitoring."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CalorCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = CalorCoordinator(hass, entry)
    await coordinator.async_load_cached_data()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    from .frontend import async_setup_frontend
    await async_setup_frontend(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove this entry's private cached reading when the account is removed."""
    from homeassistant.helpers.storage import Store

    await Store(hass, 1, f"calor_gas_snapshot_{entry.entry_id}",
                private=True, atomic_writes=True).async_remove()
