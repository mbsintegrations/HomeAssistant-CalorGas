# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Run actual cache/coordinator/sensor code with small HA lifecycle substitutes."""

import asyncio
import copy
from datetime import date, datetime, timedelta, timezone
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/calor_gas"
NOW = datetime(2024, 6, 16, 0, 10, tzinfo=timezone.utc)
RAW = {
    "account_id": "test-home", "tank_level": 57.0, "days_remaining": 365,
    "days_remaining_is_lower_bound": True, "last_reading": "2024-06-15",
    "run_out_date": "2025-06-15", "last_delivery": "2024-03-01",
    "delivery_status": "Pending Scheduling",
    "last_successful_sync": "2024-06-15T10:00:00.123456+00:00",
}


class FakeStore:
    def __init__(self, hass, version, key, **kwargs):
        self.hass, self.key = hass, key
        self.options = kwargs

    async def async_load(self):
        return copy.deepcopy(self.hass.storage.get(self.key))

    async def async_remove(self):
        self.hass.storage.pop(self.key, None)

    async def async_save(self, data):
        if self.hass.fail_save:
            raise OSError("disk error")
        self.hass.storage[self.key] = copy.deepcopy(data)


class FakeCoordinator:
    def __init__(self, hass, logger, **kwargs):
        self.hass, self.data = hass, None
        self.update_interval = kwargs["update_interval"]

    async def async_config_entry_first_refresh(self):
        self.data = await self._async_update_data()


class FakeCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


class FakeDescription:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeEntry:
    entry_id = "test-entry"
    data = {"account_id": "test-home", "username": "test-user", "password": "test-password"}

    def __init__(self):
        self.reauth_count = 0

    def async_start_reauth(self, hass):
        self.reauth_count += 1


class FakeHass:
    def __init__(self, directory):
        self.storage = {}
        self.fail_save = False
        self.config = types.SimpleNamespace(path=lambda *parts: str(Path(directory, *parts)))
        self.config_entries = types.SimpleNamespace(async_forward_entry_setups=self.forward)
        self.forwarded = False

    async def async_add_executor_job(self, fn, *args):
        return fn(*args)

    async def forward(self, entry, platforms):
        self.forwarded = True


def load_runtime():
    # Substitute only HA interfaces; execute the integration's real methods.
    replacements = {}
    def module(name, **members):
        value = types.ModuleType(name)
        value.__dict__.update(members)
        replacements[name] = value
        return value
    for name in ("homeassistant", "homeassistant.helpers", "homeassistant.components", "homeassistant.util"):
        module(name).__path__ = []
    module("homeassistant.config_entries", ConfigEntry=FakeEntry)
    module("homeassistant.core", HomeAssistant=FakeHass)
    module("homeassistant.exceptions", ConfigEntryAuthFailed=type("ConfigEntryAuthFailed", (Exception,), {}))
    module("homeassistant.helpers.aiohttp_client", async_create_clientsession=lambda *a, **k: object())
    module("homeassistant.helpers.storage", Store=FakeStore)
    module("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=FakeCoordinator,
           CoordinatorEntity=FakeCoordinatorEntity, UpdateFailed=type("UpdateFailed", (Exception,), {}))
    module("homeassistant.helpers.entity", DeviceInfo=lambda **kwargs: kwargs)
    module("homeassistant.util.dt", utcnow=lambda: NOW)
    module("homeassistant.const", Platform=types.SimpleNamespace(SENSOR="sensor"),
           EntityCategory=types.SimpleNamespace(DIAGNOSTIC="diagnostic"), UnitOfTime=types.SimpleNamespace(DAYS="d"))
    module("homeassistant.components.sensor", SensorEntity=type("SensorEntity", (), {}),
           SensorEntityDescription=FakeDescription, SensorStateClass=types.SimpleNamespace(MEASUREMENT="measurement"),
           SensorDeviceClass=types.SimpleNamespace(DURATION="duration", DATE="date", TIMESTAMP="timestamp"))
    try:
        import aiohttp
    except ImportError:
        module("aiohttp", CookieJar=lambda: object(), ClientTimeout=lambda **kwargs: object(),
               ClientError=type("ClientError", (Exception,), {}))
    prior = {name: sys.modules.get(name) for name in replacements}
    sys.modules.update(replacements)
    package = types.ModuleType("calor_runtime_test")
    package.__path__ = [str(ROOT)]
    sys.modules[package.__name__] = package
    try:
        cache = importlib.import_module("calor_runtime_test.cache")
        coordinator = importlib.import_module("calor_runtime_test.coordinator")
        sensor = importlib.import_module("calor_runtime_test.sensor")
        setup = types.ModuleType("calor_runtime_test.setup")
        setup.__package__ = "calor_runtime_test"
        exec(compile((ROOT / "__init__.py").read_text(encoding="utf-8"), str(ROOT / "__init__.py"), "exec"), setup.__dict__)
        return cache, coordinator, sensor, setup
    finally:
        for name, old in prior.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


cache, runtime, sensors, setup = load_runtime()


class CacheTests(unittest.TestCase):
    def test_round_trip_preserves_dates_sync_and_qualifier(self):
        data = cache.decode_snapshot(RAW, "test-home")
        self.assertEqual(data["last_reading"], date(2024, 6, 15))
        self.assertEqual(cache.encode_snapshot(data), RAW)

    def test_zero_is_valid_and_missing_forecasts_are_unknown(self):
        raw = dict(RAW, tank_level=0, days_remaining=None, days_remaining_is_lower_bound=False,
                   run_out_date=None, last_delivery=None, delivery_status=None)
        self.assertEqual(cache.encode_snapshot(cache.decode_snapshot(raw, "test-home")), raw)

    def test_other_account_and_extra_fields_rejected(self):
        for raw in (dict(RAW, account_id="other"), dict(RAW, password="private")):
            with self.assertRaises(ValueError):
                cache.decode_snapshot(raw, "test-home")

    def test_invalid_levels_rejected(self):
        for level in (True, -1, 101, float("nan"), float("inf"), "65"):
            with self.subTest(level=level), self.assertRaises(ValueError):
                cache.decode_snapshot(dict(RAW, tank_level=level), "test-home")

    def test_invalid_days_and_qualifiers_rejected(self):
        for changes in ({"days_remaining": True}, {"days_remaining": -1}, {"days_remaining": 1.5},
                        {"days_remaining": None}, {"days_remaining_is_lower_bound": "true"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                cache.decode_snapshot(dict(RAW, **changes), "test-home")

    def test_invalid_dates_sync_or_status_rejected(self):
        for changes in ({"last_reading": None}, {"last_reading": "bad"}, {"run_out_date": "2026-02-30"},
                        {"last_successful_sync": "2024-06-15T10:00:00"}, {"last_successful_sync": "bad"},
                        {"delivery_status": {}}, {"delivery_status": "x" * 257}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                cache.decode_snapshot(dict(RAW, **changes), "test-home")

    def test_serialization_excludes_credentials_and_transient_flags(self):
        data = cache.decode_snapshot(RAW, "test-home")
        data.update(password="private", cookie="private", data_stale=True)
        self.assertEqual(cache.encode_snapshot(data), RAW)


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.hass = FakeHass(self.directory.name)
        self.entry = FakeEntry()
        self.coordinator = runtime.CalorCoordinator(self.hass, self.entry)

    async def asyncTearDown(self):
        self.directory.cleanup()

    def portal_result(self, result):
        async def fetch():
            if isinstance(result, Exception):
                raise result
            return copy.deepcopy(result)
        self.coordinator.portal = types.SimpleNamespace(fetch=fetch)

    async def stored(self):
        self.hass.storage[self.coordinator._store.key] = copy.deepcopy(RAW)
        await self.coordinator.async_load_cached_data()

    async def test_startup_loads_cache_before_failed_first_refresh(self):
        await self.stored()
        self.portal_result(runtime.PortalError("Calor's website returned HTTP 404"))
        await self.coordinator.async_config_entry_first_refresh()
        self.assertEqual(cache.encode_snapshot(self.coordinator.data), RAW)
        self.assertTrue(self.coordinator.data_stale)
        self.assertFalse(self.coordinator.portal_available)
        self.assertEqual(self.coordinator.update_interval, timedelta(hours=6))
        self.assertEqual(self.coordinator._store.options, {"private": True, "atomic_writes": True})

    async def test_missing_cache_never_invents_value(self):
        await self.coordinator.async_load_cached_data()
        self.portal_result(runtime.PortalError("HTTP 404"))
        with self.assertRaises(runtime.UpdateFailed):
            await self.coordinator.async_config_entry_first_refresh()
        self.assertIsNone(self.coordinator.data)

    async def test_removing_entry_deletes_its_private_snapshot(self):
        await self.stored()
        old = sys.modules.get('homeassistant.helpers.storage')
        sys.modules['homeassistant.helpers.storage'] = types.SimpleNamespace(Store=FakeStore)
        try:
            await setup.async_remove_entry(self.hass, self.entry)
        finally:
            if old is None: sys.modules.pop('homeassistant.helpers.storage', None)
            else: sys.modules['homeassistant.helpers.storage'] = old
        self.assertNotIn(self.coordinator._store.key, self.hass.storage)

    async def test_corrupt_and_wrong_account_cache_are_not_used(self):
        for raw in ({"bad": True}, dict(RAW, account_id="other")):
            self.hass.storage[self.coordinator._store.key] = raw
            await self.coordinator.async_load_cached_data()
            self.assertIsNone(self.coordinator._cached_data)

    async def test_recovery_replaces_cache_and_clears_staleness(self):
        await self.stored()
        self.portal_result(runtime.PortalError("HTTP 404"))
        await self.coordinator.async_config_entry_first_refresh()
        fresh = cache.decode_snapshot(dict(RAW, tank_level=56), "test-home")
        fresh.pop("last_successful_sync")
        self.portal_result(fresh)
        await self.coordinator.async_config_entry_first_refresh()
        self.assertEqual(self.coordinator.data["tank_level"], 56)
        self.assertEqual(self.coordinator.data["last_successful_sync"], NOW)
        self.assertFalse(self.coordinator.data_stale)
        self.assertTrue(self.coordinator.portal_available)
        self.assertIsNone(self.coordinator.last_refresh_error)
        self.assertEqual(self.hass.storage[self.coordinator._store.key]["tank_level"], 56)

    async def test_success_then_failure_keeps_original_sync(self):
        fresh = cache.decode_snapshot(RAW, "test-home")
        self.portal_result(fresh)
        await self.coordinator.async_config_entry_first_refresh()
        original = self.coordinator.data.copy()
        self.portal_result(TimeoutError())
        await self.coordinator.async_config_entry_first_refresh()
        self.assertEqual(self.coordinator.data, original)
        self.assertEqual(self.hass.storage[self.coordinator._store.key], cache.encode_snapshot(original))
        self.assertTrue(self.coordinator.data_stale)

    async def test_persisted_success_restores_into_new_coordinator_during_outage(self):
        self.portal_result(cache.decode_snapshot(RAW, "test-home"))
        await self.coordinator.async_config_entry_first_refresh()
        saved = copy.deepcopy(self.hass.storage[self.coordinator._store.key])
        self.coordinator = runtime.CalorCoordinator(self.hass, self.entry)
        await self.coordinator.async_load_cached_data()
        self.portal_result(runtime.PortalError("HTTP 404"))
        await self.coordinator.async_config_entry_first_refresh()
        self.assertEqual(cache.encode_snapshot(self.coordinator.data), saved)

    async def test_wrong_account_and_invalid_fresh_data_do_not_replace_snapshot(self):
        await self.stored()
        for fresh in (cache.decode_snapshot(dict(RAW, account_id="other"), "other"),
                      dict(cache.decode_snapshot(RAW, "test-home"), tank_level=101)):
            self.portal_result(fresh)
            await self.coordinator.async_config_entry_first_refresh()
            self.assertEqual(cache.encode_snapshot(self.coordinator.data), RAW)
            self.assertEqual(self.hass.storage[self.coordinator._store.key], RAW)

    async def test_network_failure_retains_snapshot(self):
        await self.stored()
        self.portal_result(runtime.aiohttp.ClientError("network"))
        await self.coordinator.async_config_entry_first_refresh()
        self.assertEqual(cache.encode_snapshot(self.coordinator.data), RAW)
        self.assertFalse(self.coordinator.portal_available)

    async def test_auth_failure_retains_cache_and_requests_reauth(self):
        await self.stored()
        self.portal_result(runtime.AuthenticationError("bad login"))
        await self.coordinator.async_config_entry_first_refresh()
        self.assertEqual(cache.encode_snapshot(self.coordinator.data), RAW)
        self.assertEqual(self.entry.reauth_count, 1)

    async def test_auth_failure_without_cache_still_requires_reauth(self):
        self.portal_result(runtime.AuthenticationError("bad login"))
        with self.assertRaises(runtime.ConfigEntryAuthFailed):
            await self.coordinator.async_config_entry_first_refresh()

    async def test_disk_failure_does_not_lose_valid_in_memory_reading(self):
        self.hass.fail_save = True
        self.portal_result(cache.decode_snapshot(RAW, "test-home"))
        await self.coordinator.async_config_entry_first_refresh()
        self.assertEqual(self.coordinator.data["tank_level"], 57)
        self.assertTrue(self.coordinator.portal_available)

    async def test_all_sensors_keep_values_with_truthful_outage_metadata(self):
        await self.stored()
        self.portal_result(runtime.PortalError("HTTP 404"))
        await self.coordinator.async_config_entry_first_refresh()
        for description in sensors.DESCRIPTIONS:
            entity = sensors.CalorSensor(self.coordinator, description)
            self.assertTrue(entity.available)
            self.assertEqual(entity.native_value, self.coordinator.data[description.key])
            self.assertTrue(entity.extra_state_attributes["data_stale"])
            self.assertFalse(entity.extra_state_attributes["portal_available"])
            self.assertEqual(entity.extra_state_attributes["last_successful_sync"], RAW["last_successful_sync"])
        days = sensors.CalorSensor(self.coordinator, sensors.DESCRIPTIONS[1])
        self.assertTrue(days.extra_state_attributes["is_lower_bound"])

    async def test_setup_entry_loads_persistent_cache_before_forwarding_entities(self):
        self.hass.storage[self.coordinator._store.key] = copy.deepcopy(RAW)
        original = runtime.CalorPortal
        class FailingPortal:
            def __init__(self, *args):
                pass
            async def fetch(self):
                raise runtime.PortalError("HTTP 404")
        runtime.CalorPortal = FailingPortal
        try:
            await setup.async_setup_entry(self.hass, self.entry)
        finally:
            runtime.CalorPortal = original
        self.assertTrue(self.hass.forwarded)
        self.assertEqual(cache.encode_snapshot(self.entry.runtime_data.data), RAW)
