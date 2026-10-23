# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Check scoped frontend resource management and privacy-safe diagnostics."""

import importlib
import json
import sys
import types
import unittest

import test_cache

frontend=importlib.import_module("calor_runtime_test.frontend")
diagnostics=importlib.import_module("calor_runtime_test.diagnostics")

class Resources:
    def __init__(self,items=None): self.items=list(items or []);self.changes=[]
    async def async_get_info(self): return {}
    def async_items(self): return self.items
    async def async_create_item(self,data):
        self.items.append({"id":"new","type":data["res_type"],"url":data["url"]})
        self.changes.append(("create",data))
    async def async_update_item(self,key,data):
        next(i for i in self.items if i["id"]==key).update(url=data["url"],type=data["res_type"])
        self.changes.append(("update",key))
    async def async_delete_item(self,key):
        self.items=[i for i in self.items if i["id"]!=key]
        self.changes.append(("delete",key))

class FrontendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registered=[]
        async def register(paths):self.registered.extend(paths)
        self.resources=Resources()
        self.hass=types.SimpleNamespace(http=types.SimpleNamespace(async_register_static_paths=register),
            data={"lovelace":types.SimpleNamespace(resources=self.resources)})
        self.modules={}
        for name,attrs in {
            "homeassistant":{},
            "homeassistant.components":{},
            "homeassistant.components.http":{"StaticPathConfig":lambda *args:args},
            "homeassistant.components.lovelace":{},
            "homeassistant.components.lovelace.resources":{"ResourceStorageCollection":Resources},
        }.items():
            self.modules[name]=sys.modules.get(name)
            module=types.ModuleType(name);module.__dict__.update(attrs);module.__path__=[]
            sys.modules[name]=module

    async def asyncTearDown(self):
        for name,old in self.modules.items():
            if old is None:sys.modules.pop(name,None)
            else:sys.modules[name]=old

    async def test_registers_one_resource_across_reload_or_multiple_accounts(self):
        await frontend.async_setup_frontend(self.hass)
        await frontend.async_setup_frontend(self.hass)
        self.assertEqual(len(self.registered),1)
        self.assertEqual(len(self.resources.items),1)
        self.assertEqual(self.resources.items[0]["url"],frontend.CARD_URL)

    async def test_updates_only_its_own_old_resource_and_duplicates(self):
        self.resources.items=[
            {"id":"a","type":"module","url":"/calor_gas/frontend/old/calor-gas-card.js"},
            {"id":"b","type":"module","url":"/calor_gas/frontend/older/calor-gas-card.js"},
            {"id":"keep","type":"module","url":"/local/other/calor-gas-card.js"},
        ]
        await frontend.async_setup_frontend(self.hass)
        self.assertEqual(self.resources.items[0]["url"],frontend.CARD_URL)
        self.assertEqual(self.resources.items[1]["id"],"keep")
        self.assertNotIn(("delete","keep"),self.resources.changes)

    async def test_yaml_resources_are_not_modified(self):
        original=[{"url":"/example.js","type":"module"}]
        self.hass.data["lovelace"].resources=types.SimpleNamespace(data=original)
        await frontend.async_setup_frontend(self.hass)
        self.assertEqual(original,[{"url":"/example.js","type":"module"}])

    async def test_optional_frontend_failure_does_not_break_sensors(self):
        async def fail(paths):raise RuntimeError("frontend unavailable")
        self.hass.http.async_register_static_paths=fail
        await frontend.async_setup_frontend(self.hass)

    async def test_diagnostics_do_not_include_login_account_or_reading_values(self):
        coordinator=types.SimpleNamespace(data=dict(test_cache.RAW),data_stale=True,
            portal_available=False,last_refresh_error="HTTP 404")
        entry=types.SimpleNamespace(runtime_data=coordinator,
            data={"username":"private@example.invalid","password":"not-a-real-password","account_id":"test-home"})
        result=await diagnostics.async_get_config_entry_diagnostics(None,entry)
        text=json.dumps(result)
        for value in ("private@example.invalid","not-a-real-password","test-home","2024-06-15"):
            self.assertNotIn(value,text)
        self.assertTrue(result["has_saved_reading"])
