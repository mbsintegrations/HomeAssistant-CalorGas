# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Validate a last-known-good snapshot without retaining login material."""

from datetime import date, datetime
import math

FIELDS = (
    "account_id", "tank_level", "days_remaining", "days_remaining_is_lower_bound",
    "last_reading", "run_out_date", "last_delivery", "delivery_status",
    "last_successful_sync",
)


def decode_snapshot(raw, account_id):
    """Reject corrupt or other-account cache data; never invent a reading."""
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != set(FIELDS):
        raise ValueError("Invalid Calor snapshot fields")
    if raw["account_id"] != account_id:
        raise ValueError("Calor snapshot account mismatch")
    level = raw["tank_level"]
    if type(level) not in (int, float) or not math.isfinite(level) or not 0 <= level <= 100:
        raise ValueError("Invalid cached tank level")
    days = raw["days_remaining"]
    if days is not None and (type(days) is not int or days < 0):
        raise ValueError("Invalid cached days")
    lower_bound = raw["days_remaining_is_lower_bound"]
    if type(lower_bound) is not bool or (days is None and lower_bound):
        raise ValueError("Invalid cached days qualifier")
    data = dict(raw)
    for key in ("last_reading", "run_out_date", "last_delivery"):
        value = raw[key]
        if value is None and key != "last_reading":
            continue
        if not isinstance(value, str):
            raise ValueError("Invalid cached date")
        data[key] = date.fromisoformat(value)
    value = raw["last_successful_sync"]
    if not isinstance(value, str):
        raise ValueError("Invalid cached sync timestamp")
    data["last_successful_sync"] = datetime.fromisoformat(value)
    if data["last_successful_sync"].utcoffset() is None:
        raise ValueError("Cached sync timestamp needs a timezone")
    status = raw["delivery_status"]
    if status is not None and (not isinstance(status, str) or len(status) > 256):
        raise ValueError("Invalid cached delivery status")
    return data


def encode_snapshot(data):
    """Only persist approved reading fields, excluding arbitrary extra data."""
    raw = {key: data[key] for key in FIELDS}
    for key in ("last_reading", "run_out_date", "last_delivery", "last_successful_sync"):
        raw[key] = raw[key].isoformat() if raw[key] is not None else None
    decode_snapshot(raw, data["account_id"])
    return raw
