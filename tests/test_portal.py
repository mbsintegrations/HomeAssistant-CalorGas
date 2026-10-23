# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Regression checks for observed HTML and authenticated request behaviour."""

import asyncio
from datetime import date
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/calor_gas/calor_portal.py"
spec = importlib.util.spec_from_file_location("calor_portal", SOURCE)
portal = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = portal
spec.loader.exec_module(portal)

LOGIN = '''<form method="get" action="/search"><input name="query"></form>
<form method="POST" action="https://www.mycalorgas.com/login">
<input type="hidden" name="_token" value="fresh-csrf">
<input type="email" name="email"><input type="password" name="password">
</form>'''

# Structural fixture from the visible portal; no private account or login data.
TANK = '''<select id="altAccount"><option value="test-home" selected>Home</option></select>
<div class="info-panel info-panel--with-icon"><div class="info-panel__icon">
<svg id="gas-remaining-icon" data-gas-level="67"></svg>
<div class="info-panel__icon__value">67%</div></div><div class="info-panel__text">Gas remaining</div></div>
<div class="info-panel info-panel--with-icon"><div class="info-panel__icon calendar">
<div class="info-panel__icon__value">112</div></div><div class="info-panel__text">Number of days left</div></div>
<div class="info-panel"><p>Delivery status: Pending Scheduling</p>
<p>Estimated run out date: 15/06/2025</p><p>Last delivery date: 01/03/2024</p>
<p>Last reading date: 15/06/2024</p></div>'''


class ParsingTests(unittest.TestCase):
    def test_observed_structure_and_irish_dates(self):
        data = portal.parse_tank(TANK)
        self.assertEqual(data["tank_level"], 67)
        self.assertEqual(data["days_remaining"], 112)
        self.assertEqual(data["last_reading"], date(2024, 6, 15))
        self.assertEqual(data["run_out_date"], date(2025, 6, 15))
        self.assertEqual(data["account_id"], "test-home")

    def test_zero_is_a_real_reading(self):
        data = portal.parse_tank(TANK.replace('data-gas-level="67"', 'data-gas-level="0"').replace('>112<', '>0<'))
        self.assertEqual((data["tank_level"], data["days_remaining"]), (0, 0))

    def test_bad_or_missing_level_never_becomes_zero(self):
        for value in ("", "nan", "inf", "-1", "101", "unavailable"):
            with self.subTest(value=value), self.assertRaises(portal.ParseError):
                portal.parse_tank(TANK.replace('data-gas-level="67"', f'data-gas-level="{value}"'))

    def test_duplicate_gauges_are_rejected(self):
        with self.assertRaises(portal.ParseError):
            portal.parse_tank(TANK + '<svg id="gas-remaining-icon" data-gas-level="33"></svg>')

    def test_missing_forecast_is_unknown(self):
        self.assertIsNone(portal.parse_tank(TANK.replace('>112<', '>—<'))["days_remaining"])

    def test_capped_forecast_preserves_numeric_lower_bound(self):
        data = portal.parse_tank(TANK.replace('>112<', '>365+<'))
        self.assertEqual(data["days_remaining"], 365)
        self.assertTrue(data["days_remaining_is_lower_bound"])
        self.assertEqual(data["tank_level"], 67)

    def test_exact_forecast_clears_lower_bound_qualifier(self):
        for value, expected in (("112", 112), ("0", 0), ("1,234", 1234)):
            with self.subTest(value=value):
                data = portal.parse_tank(TANK.replace('>112<', f'>{value}<'))
                self.assertEqual(data["days_remaining"], expected)
                self.assertFalse(data["days_remaining_is_lower_bound"])

    def test_grouped_capped_forecast(self):
        data = portal.parse_tank(TANK.replace('>112<', '>1,234+<'))
        self.assertEqual(data["days_remaining"], 1234)
        self.assertTrue(data["days_remaining_is_lower_bound"])

    def test_missing_forecast_has_no_lower_bound(self):
        data = portal.parse_tank(TANK.replace('>112<', '>N/A<'))
        self.assertIsNone(data["days_remaining"])
        self.assertFalse(data["days_remaining_is_lower_bound"])

    def test_malformed_or_ambiguous_forecasts_fail_closed(self):
        for value in ("365++", "+365", "365 days", "365.5", "-1", "1,2", "1,,234", "365/400", "365 +"):
            with self.subTest(value=value), self.assertRaises(portal.ParseError):
                portal.parse_tank(TANK.replace('>112<', f'>{value}<'))

    def test_invalid_days_fail_closed(self):
        with self.assertRaises(portal.ParseError):
            portal.parse_tank(TANK.replace('>112<', '>tomorrow<'))

    def test_invalid_or_missing_source_date_is_rejected(self):
        for change in ('Last reading date: 31/02/2026', 'Last reading date: —'):
            with self.subTest(change=change), self.assertRaises(portal.ParseError):
                portal.parse_tank(TANK.replace('Last reading date: 15/06/2024', change))

    def test_multiple_unselected_accounts_are_rejected(self):
        changed = TANK.replace('<option value="test-home" selected>Home</option>', '<option value="one">One</option><option value="two">Two</option>')
        with self.assertRaises(portal.ParseError):
            portal.parse_tank(changed)

    def test_login_cannot_be_parsed_as_a_tank(self):
        with self.assertRaises(portal.ParseError):
            portal.parse_tank(LOGIN)

    def test_login_form_captures_csrf_and_ignores_search(self):
        action, fields = portal.login_form(LOGIN)
        self.assertEqual(action, portal.LOGIN_URL)
        self.assertEqual(fields["_token"], "fresh-csrf")
        self.assertNotIn("query", fields)

    def test_credentials_cannot_be_submitted_to_another_site(self):
        with self.assertRaises(portal.PortalError):
            portal.login_form(LOGIN.replace(portal.LOGIN_URL, 'https://example.invalid/login'))
        for target in ('http://www.mycalorgas.com/login', 'https://www.mycalorgas.com.evil.invalid/login', 'https://evil@www.mycalorgas.com/login'):
            with self.subTest(target=target), self.assertRaises(portal.PortalError):
                portal.safe_url(target)

    def test_missing_csrf_is_rejected(self):
        with self.assertRaises(portal.ParseError):
            portal.login_form(LOGIN.replace('value="fresh-csrf"', 'value=""'))


class Response:
    def __init__(self, status=200, text="", location=None):
        self.status = status
        self.body = text
        self.headers = {"Location": location} if location else {}
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def text(self):
        return self.body


class Session:
    def __init__(self, gets, posts):
        self.gets = list(gets)
        self.posts = list(posts)
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        expected, response = self.gets.pop(0)
        if url != expected:
            raise AssertionError(f"Unexpected GET path: {url}")
        return response
    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.posts.pop(0)


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_login_reads_tank_then_reuses_session(self):
        session = Session([(portal.LOGIN_URL, Response(text=LOGIN)), (portal.ORIGIN + "/dashboard", Response(text="Account initialised")), (portal.TANK_URL, Response(text=TANK)), (portal.TANK_URL, Response(text=TANK))], [Response(302, location="/dashboard")])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        self.assertEqual((await client.fetch())["tank_level"], 67)
        await client.fetch()
        posts = [x for x in session.calls if x[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][2]["data"]["_token"], "fresh-csrf")
        self.assertFalse(posts[0][2]["allow_redirects"])

    async def test_expired_session_reauthenticates_with_fresh_csrf(self):
        session = Session([(portal.TANK_URL, Response(302, location="/login")), (portal.LOGIN_URL, Response(text=LOGIN)), (portal.LOGIN_URL, Response(text=LOGIN.replace('fresh-csrf', 'renewed-csrf'))), (portal.ORIGIN + "/dashboard", Response(text="Account initialised")), (portal.TANK_URL, Response(text=TANK))], [Response(302, location="/dashboard")])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        client.authenticated = True
        await client.fetch()
        post = next(x for x in session.calls if x[0] == "POST")
        self.assertEqual(post[2]["data"]["_token"], "renewed-csrf")

    async def test_bad_password_is_not_retried_or_in_error_text(self):
        session = Session([(portal.LOGIN_URL, Response(text=LOGIN))], [Response(text=LOGIN)])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        with self.assertRaises(portal.AuthenticationError) as context:
            await client.fetch()
        self.assertNotIn("test-fixture-only", str(context.exception))
        self.assertEqual(sum(x[0] == "POST" for x in session.calls), 1)

    async def test_redirect_cannot_send_requests_to_another_site(self):
        session = Session([(portal.TANK_URL, Response(302, location="https://example.invalid/steal"))], [])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        client.authenticated = True
        with self.assertRaises(portal.PortalError):
            await client.fetch()
        self.assertEqual(len(session.calls), 1)

    async def test_rejected_login_redirect_is_not_retried(self):
        session = Session([(portal.LOGIN_URL, Response(text=LOGIN))], [Response(302, location="/login")])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        with self.assertRaises(portal.AuthenticationError):
            await client.fetch()
        self.assertEqual(sum(x[0] == "POST" for x in session.calls), 1)
        self.assertFalse(client.authenticated)

    async def test_landing_page_must_establish_authentication(self):
        session = Session([(portal.LOGIN_URL, Response(text=LOGIN)), (portal.ORIGIN + "/dashboard", Response(302, location="/login")), (portal.LOGIN_URL, Response(text=LOGIN))], [Response(302, location="/dashboard")])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        with self.assertRaises(portal.AuthenticationError):
            await client.fetch()
        self.assertFalse(client.authenticated)

    async def test_single_account_empty_context_uses_observed_dropdown_flow(self):
        tank = TANK.replace('value="test-home"', 'value="1234567"')
        empty = tank.replace('data-gas-level="67"', 'data-gas-level=""')
        session = Session([(portal.TANK_URL, Response(text=empty)), (portal.ORIGIN + "/switchacc/1234567", Response(text="OK")), (portal.ORIGIN + "/dashboard", Response(text="Account initialised")), (portal.TANK_URL, Response(text=tank))], [])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        client.authenticated = True
        self.assertEqual((await client.fetch())["tank_level"], 67)
        self.assertEqual(len(session.calls), 4)

    async def test_empty_account_context_is_retried_only_once(self):
        empty = TANK.replace('value="test-home"', 'value="1234567"').replace('data-gas-level="67"', 'data-gas-level=""')
        session = Session([(portal.TANK_URL, Response(text=empty)), (portal.ORIGIN + "/switchacc/1234567", Response(text="OK")), (portal.ORIGIN + "/dashboard", Response(text="Account initialised")), (portal.TANK_URL, Response(text=empty))], [])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        client.authenticated = True
        with self.assertRaises(portal.ParseError):
            await client.fetch()
        self.assertEqual(len(session.calls), 4)

    async def test_http_failure_has_only_safe_diagnostic(self):
        session = Session([(portal.LOGIN_URL, Response(text=LOGIN))], [Response(419, text="private response")])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        with self.assertRaises(portal.PortalError) as context:
            await client.fetch()
        self.assertEqual(str(context.exception), "Calor's sign-in returned HTTP 419")

    async def test_server_outage_is_not_reported_as_wrong_password(self):
        session = Session([(portal.LOGIN_URL, Response(503))], [])
        client = portal.CalorPortal(session, "test@example.invalid", "test-fixture-only")
        with self.assertRaises(portal.PortalError) as context:
            await client.fetch()
        self.assertNotIsInstance(context.exception, portal.AuthenticationError)


if __name__ == "__main__":
    unittest.main()
