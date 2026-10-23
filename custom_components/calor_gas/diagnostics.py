# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Minimal support diagnostics; no login, account, raw HTML or reading values."""

from .const import UPDATE_HOURS, VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    return {
        "integration_version": VERSION,
        "refresh_interval_hours": UPDATE_HOURS,
        "has_saved_reading": bool(data),
        "data_stale": coordinator.data_stale,
        "portal_available": coordinator.portal_available,
        "last_refresh_error": coordinator.last_refresh_error,
        "fields_present": {
            key: data.get(key) is not None
            for key in ("tank_level", "days_remaining", "last_reading", "last_successful_sync")
        },
    }
