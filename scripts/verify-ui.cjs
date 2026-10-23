// SPDX-FileCopyrightText: 2026 MBS Integrations
// SPDX-License-Identifier: GPL-3.0-only

const fs = require("node:fs"), path = require("node:path"), http = require("node:http"), assert = require("node:assert/strict");
const {chromium} = require("playwright");
(async () => {
  const root = path.resolve(__dirname, "..");
  const executable = [process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH, chromium.executablePath(),
    "C:/Program Files/Google/Chrome/Application/chrome.exe", "/usr/bin/google-chrome"].find(p => p && fs.existsSync(p));
  if (!executable) throw new Error("Install Chromium with: npx playwright install chromium");
  const browser = await chromium.launch({headless: true, executablePath: executable});
  const errors = [];
  const server = http.createServer((req, res) => {
    const pathname = new URL(req.url, "http://127.0.0.1").pathname;
    if (pathname === "/") {
      res.setHeader("Content-Type", "text/html");
      res.end('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#f5f7f9;font-family:Arial,sans-serif}main{padding:16px;box-sizing:border-box;margin:auto}ha-card{display:block}.dark{--primary-text-color:#ecf1f5;--secondary-text-color:#abb6c0;--ha-card-background:#202b34;--divider-color:#3a4650;background:#151e25}</style></head><body><main></main><script type="module">import "/custom_components/calor_gas/frontend/calor-gas-card.js";window.ready=true;</script></body></html>');
      return;
    }
    if (!pathname.startsWith("/custom_components/calor_gas/frontend/")) {res.writeHead(404);res.end();return;}
    const target = path.resolve(root, "." + pathname);
    if (!target.startsWith(path.join(root, "custom_components", "calor_gas", "frontend") + path.sep)) {res.writeHead(404);res.end();return;}
    res.setHeader("Content-Type", "application/javascript");res.end(fs.readFileSync(target));
  });
  await new Promise(r => server.listen(0, "127.0.0.1", r));
  try {
    const page = await browser.newPage();
    page.on("pageerror", e => errors.push(e.message));
    const brand = path.join(root, "custom_components/calor_gas/brand"); fs.mkdirSync(brand, {recursive: true});
    for (const [input, output, width, height] of [
      ["icon.svg", "icon.png", 256, 256], ["icon.svg", "icon@2x.png", 512, 512],
      ["logo.svg", "logo.png", 512, 128], ["logo.svg", "logo@2x.png", 1024, 256],
      ["logo-dark.svg", "dark_logo.png", 512, 128], ["logo-dark.svg", "dark_logo@2x.png", 1024, 256],
    ]) {
      const svg = fs.readFileSync(path.join(root, "assets", input), "utf8");
      await page.setViewportSize({width, height});
      await page.setContent('<style>body{margin:0}svg{display:block;width:' + width + 'px;height:' + height + 'px}</style>' + svg);
      await page.locator("svg").screenshot({path: path.join(brand, output), omitBackground: true});
    }
    await page.goto("http://127.0.0.1:" + server.address().port + "/");
    await page.waitForFunction(() => window.ready);
    const screenshots = path.join(root, "docs/images"); fs.mkdirSync(screenshots, {recursive: true});
    const base = {unit_of_measurement: "%", refresh_interval_hours: 6, days_remaining: 84,
      days_remaining_is_lower_bound: false, last_reading: "2024-06-15", last_successful_sync: "2024-06-15T10:00:00Z",
      run_out_date: "2024-09-07", delivery_status: "No delivery scheduled", data_stale: false, portal_available: true};
    const proof = [];
    for (const [name, value, changes, compact, viewport, cardWidth, dark, withLinks = false] of [
      ["healthy", "62", {}, false, 1280, 420, false],
      ["cached", "57", {data_stale: true, portal_available: false, days_remaining: 365, days_remaining_is_lower_bound: true}, false, 390, 358, false],
      ["low", "12", {days_remaining: 9}, false, 390, 358, false],
      ["unavailable", "unavailable", {}, false, 390, 358, false],
      ["compact", "57", {data_stale: true, portal_available: false, days_remaining: 365, days_remaining_is_lower_bound: true}, true, 390, 178, false],
      ["dark", "62", {}, false, 390, 358, true],
      ["zero", "0", {days_remaining: 0}, true, 390, 178, false],
      ["with-links", "62", {}, false, 1280, 420, false, true],
      ["dark-with-links", "62", {}, false, 390, 358, true, true],
    ]) {
      await page.setViewportSize({width: viewport, height: 620});
      await page.evaluate(({value, changes, compact, cardWidth, dark, withLinks, base}) => {
        document.body.className = dark ? "dark" : "";
        const main = document.querySelector("main"); main.style.width = cardWidth + "px"; main.style.padding = "0"; main.style.marginTop = "20px";
        const card = document.createElement(withLinks ? "calor-gas-card-with-links" : "calor-gas-card"); card.setConfig({entity: "sensor.demo_tank", compact});
        card.hass = {locale: {language: "en-IE"}, config: {time_zone: "Europe/Dublin"}, states: {
          "sensor.demo_tank": {entity_id: "sensor.demo_tank", state: value, attributes: {...base, ...changes}},
        }};
        main.replaceChildren(card); window.card = card;
      }, {value, changes, compact, cardWidth, dark, withLinks, base});
      await page.waitForTimeout(50);
      const result = await page.evaluate(() => {
        const root = window.card.shadowRoot, outer = window.card.getBoundingClientRect();
        const visible = [...root.querySelectorAll(".level,.days,.source,.badge")].filter(e => e.getBoundingClientRect().width);
        return {width: outer.width, height: outer.height, level: root.querySelector(".level").textContent,
          source: root.querySelector(".source").textContent, links: root.querySelectorAll("a").length,
          overflow: visible.some(e => {const r=e.getBoundingClientRect();return r.left < outer.left - .5 || r.right > outer.right + .5 || e.scrollWidth > e.clientWidth + 1;})};
      });
      assert.equal(result.overflow, false, name + " overflow");
      assert.equal(result.links, withLinks ? 2 : 0, name + " quick links");
      if (name === "unavailable") assert.equal(result.level, "Unavailable");
      if (name === "zero") assert.equal(result.level, "0%");
      if (name === "cached") assert.match(result.source, /Cached/);
      if (name !== "zero") await page.locator("calor-gas-card,calor-gas-card-with-links").screenshot({path: path.join(screenshots, name + ".png")});
      proof.push({scenario: name, viewport, ...result});
    }
    await page.evaluate(() => {
      window.events=[];document.addEventListener("hass-more-info",e=>window.events.push(e.detail));
      window.card.shadowRoot.querySelector(".body").click();
    });
    assert.equal(await page.evaluate(() => window.events[0].entityId), "sensor.demo_tank");
    await page.evaluate(() => {
      window.card.setConfig({entity:"sensor.demo_tank",name:'<img src=x onerror="window.__pwned=true">'});
    });
    assert.equal(await page.evaluate(() => window.__pwned), undefined);
    assert.equal(await page.locator("calor-gas-card,calor-gas-card-with-links").evaluate(c=>c.shadowRoot.querySelectorAll("img").length), 0);
    await page.evaluate(() => {
      const card = document.createElement("calor-gas-card");
      card.setConfig({entity:"sensor.demo_tank"});
      document.body.addEventListener("context-request", event => {
        if (event.target === card) event.callback({}, () => {window.unsubscribed=true;});
      });
      document.body.append(card);card.remove();
    });
    assert.equal(await page.evaluate(()=>window.unsubscribed), true);
    const editor = await page.evaluate(() => {
      const editor=document.createElement("calor-gas-card-editor");
      editor.setConfig({entity:"sensor.demo_tank"});editor.hass={states:{}};
      document.body.append(editor);
      const form=editor.shadowRoot.querySelector("ha-form");
      return form.schema.map(s=>s.name);
    });
    assert.ok(editor.includes("entity"));assert.ok(editor.includes("show_links"));assert.ok(!editor.some(s=>/password|username/.test(s)));
    const presets = await page.evaluate(() => window.customCards.filter(c => c.type.startsWith("calor-gas-card")).map(c => c.type));
    assert.deepEqual(presets, ["calor-gas-card", "calor-gas-card-with-links"]);
    assert.deepEqual(errors, []);
    fs.mkdirSync(path.join(root, "test-results"), {recursive: true});
    fs.writeFileSync(path.join(root, "test-results/ui.json"), JSON.stringify({synthetic_data: true, errors, proof, more_info_event: true, injection_safe: true, context_unsubscribe: true, visual_editor: true}, null, 2));
    console.log(JSON.stringify({scenarios: proof.length, ui_checks: "passed", logo_assets: 6, screenshots: "docs/images"},null,2));
  } finally { await browser.close(); server.close(); }
})().catch(err => {console.error(err);process.exitCode=1;});
