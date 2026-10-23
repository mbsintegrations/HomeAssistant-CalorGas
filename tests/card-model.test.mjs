// SPDX-FileCopyrightText: 2026 MBS Integrations
// SPDX-License-Identifier: GPL-3.0-only

import test from "node:test";
import assert from "node:assert/strict";
import {tankModel, validDate, validTimestamp} from "../custom_components/calor_gas/frontend/card-model.js";
const state = (value = "57", extra = {}) => ({state: value, attributes: {
  unit_of_measurement: "%", days_remaining: 365, days_remaining_is_lower_bound: true,
  last_reading: "2024-06-15", last_successful_sync: "2024-06-15T10:00:00Z",
  portal_available: true, data_stale: false, ...extra,
}});
test("numeric level, capped days and independent source/sync dates", () => {
  const model = tankModel(state());
  assert.equal(model.level, 57); assert.equal(model.days, 365); assert.equal(model.daysLowerBound, true);
  assert.equal(model.status, "Updated"); assert.equal(model.sourceDate, "2024-06-15");
});
test("zero is a real level and warning uses a strict boundary", () => {
  assert.equal(tankModel(state("0")).level, 0); assert.equal(tankModel(state("0")).low, true);
  assert.equal(tankModel(state("20")).low, false); assert.equal(tankModel(state("19.9")).low, true);
});
test("unavailable, blank, null, infinity and malformed values never become zero", () => {
  for (const value of ["", " ", "unavailable", "unknown", null, false, undefined, "NaN", Infinity, -1, 101]) {
    const candidate = state(value); candidate.state = value;
    const model = tankModel(candidate); assert.equal(model.available, false, String(value));
    assert.equal(model.level, null); assert.equal(model.low, false);
  }
});
test("outage keeps the original value and successful sync", () => {
  const model = tankModel(state("57", {data_stale: true, portal_available: false}));
  assert.equal(model.level, 57); assert.equal(model.stale, true); assert.equal(model.status, "Cached reading");
  assert.equal(model.lastSync, "2024-06-15T10:00:00Z");
});
test("fresh response clears cached presentation", () => assert.equal(tankModel(state()).stale, false));
test("missing or invalid forecasts stay unknown", () => {
  for (const value of [null, undefined, "", -1, 1.5, true]) assert.equal(tankModel(state("57", {days_remaining: value})).days, null);
});
test("date and timestamp validation rejects invalid calendar dates and naive syncs", () => {
  assert.equal(validDate("2024-02-29"), "2024-02-29"); assert.equal(validDate("2024-02-30"), null);
  assert.equal(validDate("unknown"), null); assert.equal(validTimestamp("2024-06-15T10:00:00"), null);
});
