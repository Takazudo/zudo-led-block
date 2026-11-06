#!/usr/bin/env node
// Authored-site browser checks for the built docs (doc/dist), credential-free.
//
// Serves doc/dist with Cloudflare-like static routing (<path>/index.html,
// "auto-trailing-slash" redirect, dist/404.html with HTTP 404, no SPA
// fallback) and drives Chromium through Playwright at desktop and mobile
// sizes. Fails on: non-200 pages, HTTP errors for page sub-resources, console
// errors, broken images, wrong lang/canonical, missing A5 status/BOM facts,
// broken downloads, horizontal overflow on mobile, or a missing route that is
// not a real 404. Screenshots go to test-results/screenshots/.
//
// Usage: node scripts/browser-check.mjs [--dist doc/dist] [--chromium /path]
// (CHROMIUM_PATH env also selects the browser executable.)
import http from "node:http";
import { readFile, stat, mkdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import { extname, join, resolve, normalize } from "node:path";
import { chromium } from "playwright";

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : fallback;
};
const ROOT = resolve(new URL("..", import.meta.url).pathname);
const DIST = resolve(ROOT, opt("--dist", "doc/dist"));
const OUT = resolve(ROOT, "test-results/screenshots");
const CANONICAL = "https://zudo-led-block.zudolab.dev";
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8", ".pdf": "application/pdf", ".step": "application/octet-stream",
  ".dxf": "application/dxf", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".woff2": "font/woff2", ".xml": "application/xml",
};

async function isFile(p) {
  try { return (await stat(p)).isFile(); } catch { return false; }
}

function serve() {
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");
    const path = normalize(decodeURIComponent(url.pathname));
    if (path.includes("..")) { res.writeHead(400).end(); return; }
    let file = join(DIST, path);
    if (path.endsWith("/")) file = join(file, "index.html");
    else if (!(await isFile(file)) && (await isFile(join(file, "index.html")))) {
      res.writeHead(307, { location: `${path}/${url.search}` }).end();
      return;
    }
    if (await isFile(file)) {
      res.writeHead(200, { "content-type": TYPES[extname(file).toLowerCase()] ?? "application/octet-stream" });
      res.end(req.method === "HEAD" ? undefined : await readFile(file));
      return;
    }
    res.writeHead(404, { "content-type": TYPES[".html"] });
    res.end(await readFile(join(DIST, "404.html")));
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

const PAGES = [
  { path: "/", name: "home", expect: ["Zudo LED Block"] },
  { path: "/docs/project/", name: "project", expect: ["製造リリースではありません", "部品証跡カタログ", "30 型番・81 点"] },
  { path: "/docs/project/status/", name: "status", expect: ["未配線", "130"] },
  { path: "/docs/architecture/electronics/", name: "electronics", expect: ["J3", "Qwiic", "TLV9001"] },
  { path: "/docs/architecture/bom/", name: "bom", expect: ["STM32G031G8U6TR", "C5270180", "$13.6055", "59 点"] },
  { path: "/docs/architecture/mechanical/", name: "mechanical", expect: ["29.8", "不採用"] },
  { path: "/docs/architecture/firmware/", name: "firmware", expect: ["STM32G031G8U6TR", "書込み"] },
  { path: "/docs/architecture/front-panel/", name: "front-panel", expect: ["鏡像化済み"] },
  { path: "/docs/verification/", name: "verification", expect: ["履歴"] },
  { path: "/docs/verification/historical-records/", name: "historical", expect: ["10.0.8"] },
  { path: "/docs/project/downloads/", name: "downloads", expect: ["STEP"] },
  { path: "/docs/project/hosting/", name: "hosting", expect: ["CLOUDFLARE_DEPLOY_ENABLED"] },
];

const failures = [];
const fail = (msg) => { failures.push(msg); console.error(`FAIL ${msg}`); };
const pass = (msg) => console.log(`PASS ${msg}`);

async function checkPage(context, base, page, viewport) {
  const tab = await context.newPage();
  const consoleErrors = [];
  const badResponses = [];
  tab.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  tab.on("pageerror", (e) => consoleErrors.push(String(e)));
  tab.on("response", (r) => { if (r.status() >= 400) badResponses.push(`${r.status()} ${r.url()}`); });
  tab.on("requestfailed", (r) => badResponses.push(`failed ${r.url()} ${r.failure()?.errorText}`));
  const response = await tab.goto(base + page.path, { waitUntil: "networkidle" });
  const label = `${viewport} ${page.path}`;
  if (response?.status() !== 200) fail(`${label}: HTTP ${response?.status()}`);
  const lang = await tab.getAttribute("html", "lang");
  if (lang !== "ja") fail(`${label}: html lang=${lang}`);
  if (page.path !== "/") {
    const canonical = await tab.getAttribute('link[rel="canonical"]', "href").catch(() => null);
    if (canonical !== CANONICAL + page.path) fail(`${label}: canonical=${canonical}`);
  }
  const text = await tab.locator("main, body").first().innerText();
  for (const needle of page.expect) if (!text.includes(needle)) fail(`${label}: missing text "${needle}"`);
  const images = await tab.$$eval("main img, article img", (imgs) => imgs.map((i) => ({ src: i.currentSrc || i.src, ok: i.complete && i.naturalWidth > 0 })));
  for (const img of images) if (!img.ok) fail(`${label}: broken image ${img.src}`);
  if (viewport === "mobile") {
    const overflow = await tab.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (overflow > 1) fail(`${label}: horizontal overflow ${overflow}px`);
  }
  if (consoleErrors.length) fail(`${label}: console errors ${JSON.stringify(consoleErrors.slice(0, 3))}`);
  if (badResponses.length) fail(`${label}: failed requests ${JSON.stringify(badResponses.slice(0, 3))}`);
  await tab.screenshot({ path: join(OUT, `${viewport}-${page.name}.png`), fullPage: false });
  pass(`${label} (${images.length} images)`);
  return tab;
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const executablePath = opt("--chromium", process.env.CHROMIUM_PATH) || undefined;
  const browser = await chromium.launch(executablePath ? { executablePath } : {});
  try {
    const desktop = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 });
    for (const page of PAGES) (await checkPage(desktop, base, page, "desktop")).close();
    for (const page of PAGES) (await checkPage(mobile, base, page, "mobile")).close();

    // Missing route: real HTTP 404 with the site's 404 page (no SPA fallback).
    const tab = await desktop.newPage();
    const missing = await tab.goto(`${base}/docs/no-such-page/`);
    if (missing?.status() !== 404) fail(`missing route returned HTTP ${missing?.status()}`);
    else pass("missing route returns HTTP 404");
    // Trailing-slash redirect, like Cloudflare htmlHandling auto-trailing-slash.
    const redirect = await fetch(`${base}/docs/project`, { redirect: "manual" });
    if (redirect.status !== 307 || redirect.headers.get("location") !== "/docs/project/") fail(`no-slash route: ${redirect.status}`);
    else pass("no-slash route redirects to trailing slash");

    // Header navigation reaches a nested section.
    await tab.goto(`${base}/docs/project/`, { waitUntil: "networkidle" });
    await tab.locator("header a", { hasText: "設計" }).first().click();
    await tab.waitForURL(/\/docs\/architecture\/?$/);
    pass("header navigation to 設計");

    // Search: open the dialog and find the BOM page.
    await tab.locator("[data-open-search]").first().click();
    const input = tab.locator("[data-search-input]").first();
    await input.waitFor({ state: "visible" });
    await input.fill("TLV9001");
    await tab.waitForTimeout(800);
    const hits = await tab.locator("dialog a[href*='/docs/'], [data-search-results] a, [role='dialog'] a[href*='/docs/']").count();
    if (hits === 0) fail("search for TLV9001 returned no result links");
    else pass(`search returns ${hits} result link(s)`);
    await tab.keyboard.press("Escape");

    // Theme control opens its menu.
    const theme = tab.locator("header button[aria-haspopup='menu']:visible").first();
    await theme.click();
    await tab.waitForTimeout(300);
    const items = await tab.locator("[role='menuitemradio'], [role='menuitem']").count();
    if ((await theme.getAttribute("aria-expanded")) !== "true" && items === 0) fail("theme menu did not open");
    else pass(`theme menu opens (${items} items)`);
    await tab.close();

    // Every download/image link on the downloads page serves the exact bytes.
    const dl = await desktop.newPage();
    await dl.goto(`${base}/docs/project/downloads/`, { waitUntil: "networkidle" });
    const links = [...new Set(await dl.$$eval("a[href^='/a5/']", (as) => as.map((a) => a.getAttribute("href"))))];
    if (links.length < 20) fail(`downloads page lists only ${links.length} /a5/ links`);
    for (const href of links) {
      const r = await fetch(base + href);
      const body = Buffer.from(await r.arrayBuffer());
      const local = await readFile(join(DIST, decodeURIComponent(href)));
      const same = createHash("sha256").update(body).digest("hex") === createHash("sha256").update(local).digest("hex");
      if (r.status !== 200 || !same) fail(`download ${href}: HTTP ${r.status}, identical=${same}`);
    }
    pass(`${links.length} downloads served byte-identically`);
    await dl.close();
  } finally {
    await browser.close();
    server.close();
  }
  if (failures.length) {
    console.error(`\n${failures.length} browser check failure(s)`);
    process.exit(1);
  }
  console.log("\nAll authored-site browser checks passed.");
}

main().catch((e) => { console.error(e); process.exit(1); });
