# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Exercise the real credential flow with synthetic portal replies and HA adapters."""

import importlib
import sys
import types
import unittest

import test_cache as support

class AbortFlow(Exception):
    pass

class FlowBase:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
    async def async_set_unique_id(self, value):
        self.unique_id = value
    def _abort_if_unique_id_configured(self):
        if getattr(self, "duplicate", False): raise AbortFlow("already_configured")
    def _abort_if_unique_id_mismatch(self):
        if self.unique_id != self.entry.unique_id: raise AbortFlow("unique_id_mismatch")
    def _get_reauth_entry(self): return self.entry
    def _get_reconfigure_entry(self): return self.entry
    def async_update_reload_and_abort(self, entry, data_updates):
        self.updated_data = data_updates
        return {"type": "abort", "reason": "updated"}
    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}
    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

class Schema:
    def __init__(self, schema): self.schema = schema

class Selector:
    def __init__(self, config): self.config = config

def load_flow():
    replacements = {}
    def mod(name, **data):
        result = types.ModuleType(name); result.__dict__.update(data); replacements[name] = result
        return result
    for name in ("homeassistant", "homeassistant.helpers"):
        mod(name).__path__ = []
    mod("voluptuous", Schema=Schema, Required=lambda key: key)
    mod("aiohttp", ClientError=type("ClientError", (Exception,), {}),
        CookieJar=lambda: object(), ClientTimeout=lambda **kw: object())
    mod("homeassistant.config_entries", ConfigFlow=FlowBase)
    mod("homeassistant.const", CONF_USERNAME="username", CONF_PASSWORD="password")
    mod("homeassistant.helpers.aiohttp_client", async_create_clientsession=lambda *a, **kw: None)
    mod("homeassistant.helpers.selector", TextSelector=Selector, TextSelectorConfig=lambda **kw: kw,
        TextSelectorType=types.SimpleNamespace(EMAIL="email", PASSWORD="password"))
    prior={name:sys.modules.get(name) for name in replacements}
    sys.modules.update(replacements)
    try: return importlib.import_module("calor_runtime_test.config_flow")
    finally:
        for name,value in prior.items():
            if value is None: sys.modules.pop(name,None)
            else: sys.modules[name]=value

flow_module=load_flow()
LOGIN={"username":" demo@example.invalid ", "password":"not-a-real-password"}

class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.flow=flow_module.CalorConfigFlow()
        self.flow.hass=object()
        self.flow.entry=types.SimpleNamespace(unique_id="test-home")
        self.session=types.SimpleNamespace(detached=False)
        self.session.detach=lambda: setattr(self.session,"detached",True)
        flow_module.async_create_clientsession=lambda *a,**kw:self.session
        self.reply={"account_id":"test-home"}
        self.calls=0
        owner=self
        class Portal:
            def __init__(self,*args): pass
            async def fetch(self):
                owner.calls+=1
                if isinstance(owner.reply,Exception): raise owner.reply
                return owner.reply
        flow_module.CalorPortal=Portal

    async def test_all_credential_dialogs_have_email_and_masked_password(self):
        for method in (self.flow.async_step_user,self.flow.async_step_reconfigure,self.flow.async_step_reauth_confirm):
            result=await method()
            fields=result["data_schema"].schema
            self.assertEqual(fields["username"].config["type"],"email")
            self.assertEqual(fields["password"].config["type"],"password")
            self.assertEqual(result["type"],"form")

    async def test_success_discovers_account_and_strips_email(self):
        result=await self.flow.async_step_user(LOGIN)
        self.assertEqual(result["type"],"create_entry")
        self.assertEqual(result["data"]["account_id"],"test-home")
        self.assertEqual(result["data"]["username"],"demo@example.invalid")
        self.assertTrue(self.session.detached)

    async def test_empty_password_does_not_contact_portal(self):
        result=await self.flow.async_step_user(dict(LOGIN,password=""))
        self.assertEqual(result["errors"]["base"],"invalid_auth")
        self.assertEqual(self.calls,0)

    async def test_reauth_and_reconfigure_preserve_same_account(self):
        for method in (self.flow.async_step_reauth_confirm,self.flow.async_step_reconfigure):
            result=await method(LOGIN)
            self.assertEqual(result["type"],"abort")
            self.assertEqual(self.flow.updated_data["account_id"],"test-home")

    async def test_other_account_is_rejected_during_reauthentication(self):
        self.reply={"account_id":"other"}
        with self.assertRaisesRegex(AbortFlow,"unique_id_mismatch"):
            await self.flow.async_step_reauth_confirm(LOGIN)
        self.assertTrue(self.session.detached)

    async def test_duplicate_setup_is_rejected(self):
        self.flow.duplicate=True
        with self.assertRaisesRegex(AbortFlow,"already_configured"):
            await self.flow.async_step_user(LOGIN)

    async def test_bad_login_shows_safe_error(self):
        self.reply=flow_module.AuthenticationError("Sign-in rejected")
        result=await self.flow.async_step_user(LOGIN)
        self.assertEqual(result["errors"]["base"],"invalid_auth")
        self.assertNotIn(LOGIN["password"],str(result))

    async def test_transport_failure_keeps_the_dialog_open(self):
        self.reply=flow_module.aiohttp.ClientError()
        result=await self.flow.async_step_user(LOGIN)
        self.assertEqual(result["errors"]["base"],"cannot_connect")
        self.assertTrue(self.session.detached)

    async def test_website_outage_is_not_reported_as_wrong_password(self):
        self.reply=flow_module.PortalError("Calor's website returned HTTP 404")
        result=await self.flow.async_step_user(LOGIN)
        self.assertEqual(result["errors"]["base"],"portal_changed")
        self.assertNotIn(LOGIN["password"],str(result))
