# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Serve and register the bundled card through Home Assistant APIs."""

import asyncio
import logging
from pathlib import Path

from .const import CARD_PATH, CARD_URL, DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_setup_frontend(hass):
    """Optional frontend failure must not prevent tank monitoring."""
    if not getattr(hass, "http", None):
        return
    try:
        from homeassistant.components.http import StaticPathConfig
        from homeassistant.components.lovelace.resources import ResourceStorageCollection

        state = hass.data.setdefault(DOMAIN, {})
        async with state.setdefault("frontend_lock", asyncio.Lock()):
            if not state.get("frontend_registered"):
                await hass.http.async_register_static_paths([
                    StaticPathConfig(CARD_PATH, str(Path(__file__).parent / "frontend"), True)
                ])
                state["frontend_registered"] = True
            resources = getattr(hass.data.get("lovelace"), "resources", None)
            if not isinstance(resources, ResourceStorageCollection):
                LOGGER.info("Add the Calor card resource manually: %s (module)", CARD_URL)
                return
            await resources.async_get_info()
            matches = [
                item for item in resources.async_items()
                if item.get("url", "").split("?")[0].startswith("/calor_gas/frontend/")
                and item.get("url", "").split("?")[0].endswith("/calor-gas-card.js")
            ]
            if not matches:
                await resources.async_create_item({"res_type": "module", "url": CARD_URL})
                return
            first = matches[0]
            if first.get("url") != CARD_URL or first.get("type") != "module":
                await resources.async_update_item(
                    first["id"], {"res_type": "module", "url": CARD_URL}
                )
            for duplicate in matches[1:]:
                await resources.async_delete_item(duplicate["id"])
    except Exception as err:
        LOGGER.warning(
            "Calor sensors are available but card registration failed (%s). "
            "See the manual resource instructions in the README.", type(err).__name__
        )
