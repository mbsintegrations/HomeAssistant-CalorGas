// SPDX-FileCopyrightText: 2026 MBS Integrations
// SPDX-License-Identifier: GPL-3.0-only

import {tankModel, displayDate, displaySync} from "./card-model.js";

const TANK = '<svg viewBox="0 0 160 130" aria-hidden="true"><defs><clipPath id="gas-body"><rect x="9" y="42" width="142" height="66" rx="33"/></clipPath><linearGradient id="gas-metal" x2="0" y2="1"><stop stop-color="#f7fafc"/><stop offset="1" stop-color="#c9d1d8"/></linearGradient></defs><path d="M39 106v15m82-15v15" stroke="#b6c0c9" stroke-width="6" stroke-linecap="round"/><rect x="67" y="24" width="26" height="20" rx="5" fill="#e7ecef" stroke="#b6c0c9" stroke-width="2"/><path d="M74 24v-5h12v5" fill="none" stroke="#b6c0c9" stroke-width="3"/><rect x="9" y="42" width="142" height="66" rx="33" fill="url(#gas-metal)"/><g clip-path="url(#gas-body)"><rect id="gas-fill" x="9" y="108" width="142" height="0" fill="#df352f"/><path d="M12 50h136" stroke="#ffffff" opacity=".65" stroke-width="3"/></g><rect x="9" y="42" width="142" height="66" rx="33" fill="none" stroke="#a8b3bc" stroke-width="2"/></svg>';
const STYLES = [
  ":host{display:block;--gas-accent:#df352f;color:var(--primary-text-color,#1c2733);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif)}",
  "ha-card{display:block;padding:18px;border-radius:18px;background:var(--ha-card-background,var(--card-background-color,#fff));border:1px solid var(--divider-color,#e1e5e8);box-sizing:border-box;overflow:hidden}",
  "ha-card.low{border-color:#d9383270;background:linear-gradient(140deg,#df352f0d,transparent)}",
  "header{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}",
  "h2{font-size:17px;line-height:24px;font-weight:650;margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
  ".badge{font-size:11px;font-weight:600;white-space:nowrap;padding:4px 8px;border-radius:12px;background:#2e7d3212;color:var(--primary-text-color,#1c2733);flex-shrink:0}",
  ".cached .badge{background:#b56d0015}.unavailable .badge{background:#7a879012;color:var(--secondary-text-color,#6e7882)}",
  ".body{display:grid;grid-template-columns:minmax(76px,118px) minmax(0,1fr);gap:18px;align-items:center;min-height:104px;cursor:pointer;border-radius:10px;outline-offset:3px}",
  ".tank{width:100%;align-self:center}.tank svg{display:block;width:100%;filter:drop-shadow(0 4px 4px #0d20300c)}",
  ".metrics{min-width:0}.level{font-size:38px;font-weight:700;line-height:1.1;letter-spacing:-1px;white-space:nowrap}.low .level{color:#d32f2f}",
  ".unavailable .level{font-size:22px;letter-spacing:0}.compact.unavailable .level{font-size:13px}.days{font-size:14px;line-height:23px;font-weight:600;margin-top:3px}.source{font-size:12px;color:var(--secondary-text-color,#6e7882);line-height:18px;margin-top:3px}",
  ".notice{font-size:12px;line-height:18px;color:var(--secondary-text-color,#6e7882);padding:8px 0 2px}",
  ".notice strong{color:var(--primary-text-color,#1c2733);font-weight:600}details{border-top:1px solid var(--divider-color,#e1e5e8);margin-top:12px;padding-top:10px}",
  "summary{cursor:pointer;font-size:12px;color:var(--secondary-text-color,#6e7882)}dl{display:grid;grid-template-columns:1fr 1.2fr;gap:7px 10px;font-size:12px;margin:12px 0 0;line-height:18px}dt{color:var(--secondary-text-color,#6e7882)}dd{margin:0;text-align:right;overflow-wrap:anywhere}",
  "a{color:var(--primary-color,#168bb0);font-size:12px;text-decoration:none}.links{display:flex;justify-content:space-between;gap:12px;margin-top:12px}",
  "ha-card.compact{padding:10px 12px;min-height:94px}ha-card.compact header{display:none}ha-card.compact .body{min-height:72px;grid-template-columns:minmax(44px,64px) minmax(0,1fr);gap:8px}ha-card.compact .level{font-size:28px}ha-card.compact .days{font-size:12px;line-height:18px}ha-card.compact .source{font-size:11px;line-height:16px}.compact .notice,.compact .links,.compact details{display:none}",
  "@media(max-width:360px){.body{gap:12px}.level{font-size:34px}ha-card{padding:14px}}",
].join("\n");

function element(tag, className, text) {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text !== undefined) value.textContent = text;
  return value;
}

export class CalorGasCard extends HTMLElement {
  constructor() { super(); this.attachShadow({mode: "open"}); }
  static getConfigElement() { return document.createElement("calor-gas-card-editor"); }
  static getStubConfig(hass) {
    const entity = Object.values(hass?.states || {}).find(s =>
      s.attributes?.unit_of_measurement === "%" && s.attributes?.refresh_interval_hours === 6
      && "last_successful_sync" in s.attributes);
    return {type: "custom:calor-gas-card", entity: entity?.entity_id || "", show_details: true};
  }
  setConfig(config) {
    if (!config || typeof config.entity !== "string" || !/^sensor\.[a-z0-9_]+$/.test(config.entity)) {
      throw new Error("Select the Calor Gas tank level sensor.");
    }
    const threshold = config.low_threshold ?? 20;
    if (typeof threshold !== "number" || !Number.isFinite(threshold) || threshold < 0 || threshold > 100) {
      throw new Error("Low-level threshold must be between 0 and 100.");
    }
    this._config = {name: "Calor Gas", show_details: true, show_links: false, compact: false, ...config};
    this._render();
  }
  set hass(value) { this._hass = value; this._states = value?.states; this._render(); }
  connectedCallback() {
    if (!this._unsubscribe) {
      const request = new CustomEvent("context-request", {bubbles: true, composed: true, cancelable: true});
      request.context = "states";
      request.subscribe = true;
      request.callback = (states, unsubscribe) => {
        this._states = states; this._unsubscribe = unsubscribe; this._render();
      };
      this.dispatchEvent(request);
    }
    this._render();
  }
  disconnectedCallback() { this._unsubscribe?.(); this._unsubscribe = undefined; }
  getCardSize() { return this._config?.compact ? 2 : this._config?.show_details ? 5 : 3; }
  getGridOptions() { return {columns: this._config?.compact ? 6 : 12, min_columns: 6, min_rows: this._config?.compact ? 2 : 3}; }
  _moreInfo() {
    this.dispatchEvent(new CustomEvent("hass-more-info", {
      bubbles: true, composed: true, detail: {entityId: this._config.entity},
    }));
  }
  _render() {
    if (!this._config) return;
    const data = tankModel(this._states?.[this._config.entity], this._config);
    const locale = this._hass?.locale?.language || navigator.language || "en";
    const timezone = this._hass?.config?.time_zone;
    const card = element("ha-card", [
      data.low ? "low" : "", data.stale ? "cached" : "", !data.available ? "unavailable" : "",
      this._config.compact ? "compact" : "",
    ].join(" "));
    const header = element("header");
    header.append(element("h2", "", this._config.name), element("span", "badge", data.status));
    const body = element("div", "body");
    body.tabIndex = 0; body.setAttribute("role", "button");
    body.setAttribute("aria-label", "Open Calor Gas reading details");
    body.addEventListener("click", () => this._moreInfo());
    body.addEventListener("keydown", e => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this._moreInfo(); }
    });
    const tank = element("div", "tank"); tank.innerHTML = TANK;
    tank.querySelector("#gas-fill").setAttribute("height", data.available ? String(data.level * .66) : "0");
    tank.querySelector("#gas-fill").setAttribute("y", data.available ? String(108 - data.level * .66) : "108");
    const metrics = element("div", "metrics");
    const formatted = data.available ? new Intl.NumberFormat(locale, {maximumFractionDigits: 1}).format(data.level) + "%" : "Unavailable";
    const daysText = data.days === null ? (this._config.compact ? "Days unknown" : "Days remaining unknown")
      : new Intl.NumberFormat(locale).format(data.days) + (data.daysLowerBound ? "+" : "") + " days left";
    metrics.append(element("div", "level", formatted), element("div", "days", daysText));
    let source = data.stale ? "Cached" : "Read";
    const sourceDate = data.sourceDate && this._config.compact
      ? new Intl.DateTimeFormat(locale, {day: "numeric", month: "short", timeZone: "UTC"}).format(new Date(data.sourceDate + "T00:00:00Z"))
      : displayDate(data.sourceDate, locale);
    source += data.sourceDate ? " \u00b7 " + sourceDate : " \u00b7 no reading date";
    if (!data.available) source = "No saved reading";
    const sourceNode = element("div", "source", source);
    sourceNode.title = "Last successful refresh: " + displaySync(data.lastSync, locale, timezone);
    metrics.append(sourceNode);
    body.append(tank, metrics); card.append(header, body);
    if (data.stale) {
      const notice = element("div", "notice");
      notice.append(element("strong", "", "Showing the last saved reading. "));
      notice.append(document.createTextNode("Last refreshed " + displaySync(data.lastSync, locale, timezone) + "."));
      card.append(notice);
    }
    if (!data.available) card.append(element("div", "notice", "Waiting for the first successful MyCalorGas reading."));
    if (this._config.show_details && !this._config.compact) {
      const details = element("details"); details.open = this._detailsOpen || false;
      details.addEventListener("toggle", () => { this._detailsOpen = details.open; });
      details.append(element("summary", "", "Reading details"));
      const list = element("dl");
      for (const [label, value] of [
        ["Source reading", displayDate(data.sourceDate, locale)],
        ["Last refreshed", displaySync(data.lastSync, locale, timezone)],
        ["Estimated run-out", displayDate(data.runOutDate, locale)],
        ["Delivery status", data.deliveryStatus || "\u2014"],
      ]) list.append(element("dt", "", label), element("dd", "", value));
      details.append(list); card.append(details);
    }
    if (this._config.show_links) {
      const links = element("div", "links");
      const portal = element("a", "", "MyCalorGas"); portal.href = "https://www.mycalorgas.com/TankDelivery";
      portal.target = "_blank"; portal.rel = "noopener noreferrer";
      const setup = element("a", "", "Integration settings"); setup.href = "/config/integrations/integration/calor_gas";
      links.append(portal, setup); card.append(links);
    }
    const style = element("style"); style.textContent = STYLES;
    this.shadowRoot.replaceChildren(style, card);
  }
}

class CalorGasCardWithLinks extends CalorGasCard {
  static getStubConfig(hass) {
    return {...super.getStubConfig(hass), type: "custom:calor-gas-card-with-links", show_links: true};
  }
  setConfig(config) { super.setConfig({show_links: true, ...config}); }
}

class CalorGasCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode: "open"}); }
  setConfig(config) { this._config = {...config}; this._render(); }
  set hass(value) { this._hass = value; this._render(); }
  _render() {
    if (!this._config || !this._hass) return;
    const form = document.createElement("ha-form"); form.hass = this._hass; form.data = this._config;
    form.schema = [
      {name: "entity", required: true, selector: {entity: {filter: [{domain: "sensor", integration: "calor_gas"}]}}},
      {name: "name", selector: {text: {}}},
      {name: "compact", selector: {boolean: {}}},
      {name: "show_details", selector: {boolean: {}}},
      {name: "show_links", selector: {boolean: {}}},
      {name: "low_threshold", selector: {number: {min: 0, max: 100, step: 1, mode: "box", unit_of_measurement: "%"}}},
    ];
    const labels = {entity: "Tank level sensor", name: "Card title", compact: "Compact layout",
      show_details: "Show reading details", show_links: "Show quick links", low_threshold: "Low-level warning below"};
    form.computeLabel = schema => labels[schema.name] || schema.name;
    form.addEventListener("value-changed", event => {
      event.stopPropagation(); this._config = {...event.detail.value, type: this._config.type || "custom:calor-gas-card"};
      this.dispatchEvent(new CustomEvent("config-changed", {detail: {config: this._config}, bubbles: true, composed: true}));
    });
    this.shadowRoot.replaceChildren(form);
  }
}

if (!customElements.get("calor-gas-card")) customElements.define("calor-gas-card", CalorGasCard);
if (!customElements.get("calor-gas-card-with-links")) customElements.define("calor-gas-card-with-links", CalorGasCardWithLinks);
if (!customElements.get("calor-gas-card-editor")) customElements.define("calor-gas-card-editor", CalorGasCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "calor-gas-card")) window.customCards.push({
  type: "calor-gas-card", name: "Calor Gas tank", description: "Tank level, remaining days and saved readings without footer links.", preview: true,
});

if (!window.customCards.some(card => card.type === "calor-gas-card-with-links")) window.customCards.push({
  type: "calor-gas-card-with-links", name: "Calor Gas tank with links", description: "Tank readings with MyCalorGas and integration settings links.", preview: true,
});
