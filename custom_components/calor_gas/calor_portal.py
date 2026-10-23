# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Read MyCalorGas through its normal login, using an isolated HTTP session.

No portal account changes or orders are made. Credentials, cookies, tokens and
response bodies are never logged or saved by this module.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
import math
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

ORIGIN = "https://www.mycalorgas.com"
LOGIN_URL = ORIGIN + "/login"
TANK_URL = ORIGIN + "/TankDelivery"
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class PortalError(Exception):
    """The portal could not provide a usable reading."""


class AuthenticationError(PortalError):
    """Calor did not accept the credentials."""


class ParseError(PortalError):
    """Expected portal fields are missing or invalid."""


@dataclass
class Node:
    tag: str
    attrs: dict[str, str | None] = field(default_factory=dict)
    parts: list[Any] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(" ".join(p.text if isinstance(p, Node) else p for p in self.parts).split())

    def find(self, predicate):
        if predicate(self):
            yield self
        for part in self.parts:
            if isinstance(part, Node):
                yield from part.find(predicate)

    def has_class(self, value: str) -> bool:
        return value in (self.attrs.get("class") or "").split()


class Document(HTMLParser):
    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].parts.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].parts.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack[-1].tag not in {"script", "style"}:
            self.stack[-1].parts.append(data)


def safe_url(url: str) -> str:
    """Only send requests to the portal's HTTPS origin."""
    resolved = urljoin(ORIGIN, url)
    parsed = urlsplit(resolved)
    if (parsed.scheme != "https" or parsed.netloc != "www.mycalorgas.com"
            or parsed.username is not None or parsed.password is not None):
        raise PortalError("Calor returned an unexpected redirect destination")
    return resolved


def login_form(html: str) -> tuple[str, dict[str, str]]:
    root = Document(html).root
    for form in root.find(lambda n: n.tag == "form"):
        if (form.attrs.get("method") or "get").lower() != "post":
            continue
        fields = {
            n.attrs["name"]: n.attrs.get("value") or ""
            for n in form.find(lambda n: n.tag == "input")
            if n.attrs.get("name") and "disabled" not in n.attrs
            and (n.attrs.get("type") or "text").lower() not in {"submit", "button", "reset"}
        }
        if "email" not in fields or "password" not in fields:
            continue
        action = safe_url(form.attrs.get("action") or LOGIN_URL)
        if urlsplit(action).path != "/login" or not fields.get("_token"):
            raise ParseError("Calor's login form has changed")
        return action, fields
    raise ParseError("Calor's login form was not found")


def is_login(html: str, url: str) -> bool:
    if urlsplit(url).path.rstrip("/").lower() == "/login":
        return True
    return any(n.attrs.get("name") == "password" for n in Document(html).root.find(lambda n: n.tag == "input"))


def parse_tank(html: str) -> dict[str, Any]:
    """Extract the observed tank markup; missing numbers never become zero."""
    root = Document(html).root
    gauges = list(root.find(lambda n: n.attrs.get("id") == "gas-remaining-icon"))
    if len(gauges) != 1:
        raise ParseError("Calor's tank level was not found uniquely")
    try:
        level = float(gauges[0].attrs.get("data-gas-level") or "")
    except ValueError as err:
        raise ParseError("Calor's tank level is not numeric") from err
    if not math.isfinite(level) or not 0 <= level <= 100:
        raise ParseError("Calor's tank level is outside 0–100 percent")

    panels = list(root.find(lambda n: n.has_class("info-panel")))
    day_panels = [n for n in panels if "number of days left" in n.text.lower()]
    if len(day_panels) != 1:
        raise ParseError("Calor's remaining-days panel was not found uniquely")
    values = list(day_panels[0].find(lambda n: n.has_class("info-panel__icon__value")))
    days_raw = values[0].text if len(values) == 1 else ""
    # Calor caps long forecasts as e.g. "365+". Keep the numeric lower bound
    # and its qualifier separately so duration sensors stay numeric and the
    # dashboard can display the portal's estimate without losing the plus.
    # Missing forecasts are unknown; unexpected text still fails closed.
    days_is_lower_bound = False
    if days_raw.strip().lower() in {"", "-", "—", "n/a"}:
        days = None
    else:
        match = re.fullmatch(r"([0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(\+)?", days_raw)
        if not match:
            raise ParseError("Calor's remaining-days value is invalid")
        days = int(match.group(1).replace(",", ""))
        days_is_lower_bound = match.group(2) is not None

    details: dict[str, str] = {}
    for node in root.find(lambda n: n.tag == "p"):
        label, separator, value = node.text.partition(":")
        if separator:
            details[label.strip().lower()] = value.strip()

    def portal_date(label: str, required: bool = False) -> date | None:
        raw = details.get(label, "")
        if raw.lower() in {"", "-", "—", "n/a"}:
            if required:
                raise ParseError("Calor's last reading date is missing")
            return None
        try:
            return datetime.strptime(raw, "%d/%m/%Y").date()
        except ValueError as err:
            raise ParseError("Calor returned an invalid date") from err

    accounts = list(root.find(lambda n: n.tag == "select" and n.attrs.get("id") == "altAccount"))
    if len(accounts) != 1:
        raise ParseError("Calor's selected account was not found uniquely")
    choices = list(accounts[0].find(lambda n: n.tag == "option"))
    selected = [n for n in choices if "selected" in n.attrs]
    if not selected and len(choices) == 1:
        selected = choices
    if len(selected) != 1 or not selected[0].attrs.get("value"):
        raise ParseError("Calor's selected account is ambiguous")

    return {
        "account_id": selected[0].attrs["value"],
        "tank_level": level,
        "days_remaining": days,
        "days_remaining_is_lower_bound": days_is_lower_bound,
        "last_reading": portal_date("last reading date", required=True),
        "run_out_date": portal_date("estimated run out date"),
        "last_delivery": portal_date("last delivery date"),
        "delivery_status": details.get("delivery status") or None,
    }


class CalorPortal:
    """Maintain session cookies in memory and re-login once after expiry."""

    def __init__(self, session, email: str, password: str):
        self.session = session
        self.email = email
        self.password = password
        self.authenticated = False
        self.lock = asyncio.Lock()

    async def _get(self, url: str) -> tuple[str, str]:
        for _ in range(5):
            url = safe_url(url)
            async with self.session.get(url, allow_redirects=False) as response:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        raise PortalError("Calor returned an incomplete redirect")
                    url = safe_url(urljoin(url, location))
                    continue
                if response.status in {401, 403}:
                    raise AuthenticationError("Calor requires sign-in")
                if response.status != 200:
                    raise PortalError(f"Calor's website returned HTTP {response.status}")
                return await response.text(), url
        raise PortalError("Calor returned too many redirects")

    async def _login(self) -> None:
        html, _ = await self._get(LOGIN_URL)
        action, fields = login_form(html)
        fields.update(email=self.email, password=self.password)
        async with self.session.post(
            action, data=fields, allow_redirects=False,
            headers={"Origin": ORIGIN, "Referer": LOGIN_URL},
        ) as response:
            if response.status in {301, 302, 303}:
                destination = safe_url(response.headers.get("Location") or LOGIN_URL)
                if urlsplit(destination).path.rstrip("/").lower() == "/login":
                    raise AuthenticationError("Calor did not accept the sign-in")
            elif response.status in {200, 401, 403, 422}:
                raise AuthenticationError("Calor did not accept the sign-in")
            else:
                raise PortalError(f"Calor's sign-in returned HTTP {response.status}")
        # Complete the same landing-page redirect as a browser. The portal can
        # initialise the selected account there before TankDelivery is opened.
        landing_html, landing_url = await self._get(destination)
        if is_login(landing_html, landing_url):
            raise AuthenticationError("Calor did not establish a signed-in session")
        self.authenticated = True

    async def fetch(self) -> dict[str, Any]:
        async with self.lock, asyncio.timeout(60):
            if not self.authenticated:
                await self._login()
            html, url = await self._get(TANK_URL)
            if is_login(html, url):
                self.authenticated = False
                await self._login()
                html, url = await self._get(TANK_URL)
                if is_login(html, url):
                    self.authenticated = False
                    raise AuthenticationError("Calor did not establish a signed-in session")
            # Calor's account dropdown calls GET switchacc/<account> and then
            # opens /dashboard. A fresh session may have one account but no
            # tank context. Follow that observed dropdown flow once, only for
            # an empty gauge and a single unambiguous numeric account.
            root = Document(html).root
            gauges = list(root.find(lambda n: n.attrs.get("id") == "gas-remaining-icon"))
            accounts = list(root.find(lambda n: n.tag == "select" and n.attrs.get("id") == "altAccount"))
            choices = list(accounts[0].find(lambda n: n.tag == "option")) if len(accounts) == 1 else []
            if (len(gauges) == 1 and not (gauges[0].attrs.get("data-gas-level") or "").strip()
                    and len(choices) == 1
                    and re.fullmatch(r"\d{1,30}", choices[0].attrs.get("value") or "")):
                await self._get(ORIGIN + "/switchacc/" + choices[0].attrs["value"])
                await self._get(ORIGIN + "/dashboard")
                html, url = await self._get(TANK_URL)
                if is_login(html, url):
                    self.authenticated = False
                    raise AuthenticationError("Calor did not establish a signed-in session")
            return parse_tank(html)
