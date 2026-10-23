// SPDX-FileCopyrightText: 2026 MBS Integrations
// SPDX-License-Identifier: GPL-3.0-only

/** Pure presentation rules shared by the card and its tests. */
export function tankModel(state, config = {}) {
  const raw = state?.state;
  const numeric = typeof raw === "number" || (typeof raw === "string" && raw.trim() !== "");
  const level = numeric ? Number(raw) : NaN;
  const available = numeric && Number.isFinite(level) && level >= 0 && level <= 100
    && state?.attributes?.unit_of_measurement === "%";
  const attributes = state?.attributes || {};
  const candidate = attributes.days_remaining;
  const days = typeof candidate === "number" && Number.isInteger(candidate) && candidate >= 0 ? candidate : null;
  const stale = available && (attributes.data_stale === true || attributes.portal_available === false);
  const threshold = config.low_threshold ?? 20;
  return {
    available, level: available ? level : null, stale,
    low: available && level < threshold,
    days: available ? days : null,
    daysLowerBound: available && days !== null && attributes.days_remaining_is_lower_bound === true,
    sourceDate: available ? validDate(attributes.last_reading) : null,
    runOutDate: available ? validDate(attributes.run_out_date) : null,
    lastSync: available ? validTimestamp(attributes.last_successful_sync) : null,
    deliveryStatus: available && typeof attributes.delivery_status === "string" ? attributes.delivery_status : null,
    error: stale && typeof attributes.last_refresh_error === "string" ? attributes.last_refresh_error : null,
    status: !available ? "Unavailable" : stale ? "Cached reading" : "Updated",
  };
}

export function validDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(value + "T00:00:00Z");
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? value : null;
}

export function validTimestamp(value) {
  return typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value)
    && Number.isFinite(Date.parse(value)) ? value : null;
}

export function displayDate(value, locale = "en") {
  if (!value) return "\u2014";
  try {
    return new Intl.DateTimeFormat(locale.replace("_", "-"), {dateStyle: "medium", timeZone: "UTC"})
      .format(new Date(value + "T00:00:00Z"));
  } catch { return value; }
}

export function displaySync(value, locale = "en", timeZone) {
  if (!value) return "\u2014";
  try {
    return new Intl.DateTimeFormat(locale.replace("_", "-"),
      {dateStyle: "medium", timeStyle: "short", ...(timeZone ? {timeZone} : {})}).format(new Date(value));
  } catch { return value; }
}
