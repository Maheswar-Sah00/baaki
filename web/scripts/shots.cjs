// Design QA screenshots (dev tool, not shipped).
//   node scripts/shots.cjs <outDir> <route> [route...] [--desktop] [--mobile] [--full] [--dark-only] [--light-only]
// Defaults: both themes, both viewports (mobile 390x844 @2x, desktop 1440x900), viewport-only.
// Base URL: BAAKI_URL (default http://localhost:3013, the shared dev server). Uses Playwright from B:/Projects/appwrite.
// API_URL (optional): send the browser's /api/* calls to this backend instead (e.g. a private review
// backend with its own throwaway database), so screenshots never write to the demo or shared dev data.
// FAKE_AUDIO=1 adds an audio_url to employer payloads so the voice-note player renders.
// UI_LANG=te|hi-en|en presets the app language.
// Example: node scripts/shots.cjs B:/tmp/shots/site / --desktop --full
const path = require("path");
const fs = require("fs");
const { chromium } = require("B:/Projects/appwrite/node_modules/playwright");

const args = process.argv.slice(2);
const out = args.shift();
const flags = new Set(args.filter((a) => a.startsWith("--")));
const routes = args.filter((a) => !a.startsWith("--"));
const base = process.env.BAAKI_URL || "http://localhost:3013";
const viewports = [];
if (!flags.has("--desktop") || flags.has("--mobile")) viewports.push({ name: "m", width: 390, height: 844, scale: 2, mobile: true });
if (!flags.has("--mobile") || flags.has("--desktop")) viewports.push({ name: "d", width: 1440, height: 900, scale: 1, mobile: false });
const themes = flags.has("--dark-only") ? ["dark"] : flags.has("--light-only") ? ["light"] : ["light", "dark"];

(async () => {
  fs.mkdirSync(out, { recursive: true });
  let browser;
  try {
    browser = await chromium.launch({ channel: "msedge" });
  } catch {
    browser = await chromium.launch();
  }
  for (const vp of viewports) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: vp.scale,
      isMobile: vp.mobile,
      hasTouch: vp.mobile,
      reducedMotion: "no-preference",
    });
    if (process.env.API_URL) {
      await ctx.route("**/api/**", async (route) => {
        const u = new URL(route.request().url());
        try {
          const resp = await route.fetch({ url: process.env.API_URL.replace(/\/$/, "") + u.pathname + u.search });
          if (process.env.FAKE_AUDIO && /^\/api\/(e|raise\/e)\/[^/]+$/.test(u.pathname) && route.request().method() === "GET") {
            const j = await resp.json();
            if (j && !j.audio_url) j.audio_url = "/api/media/demo.ogg";
            // drop the original length header: the edited body is longer
            const headers = { ...resp.headers() };
            delete headers["content-length"];
            await route.fulfill({ status: resp.status(), headers, json: j });
          } else await route.fulfill({ response: resp });
        } catch {
          await route.abort();
        }
      });
    }
    if (process.env.UI_LANG) {
      await ctx.addInitScript((l) => {
        try { localStorage.setItem("baaki.settings.v1", JSON.stringify({ workerId: 1, uiLang: l, listenLang: "auto" })); } catch {}
      }, process.env.UI_LANG);
    }
    const page = await ctx.newPage();
    for (const r of routes) {
      for (const t of themes) {
        const sep = r.includes("?") ? "&" : "?";
        const url = `${base}${r}${sep}theme=${t}`;
        const errors = [];
        page.removeAllListeners("pageerror");
        page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
        try {
          await page.goto(url, { waitUntil: "networkidle", timeout: 90000 });
        } catch (e) {
          console.log("WARN goto", url, String(e).slice(0, 120));
        }
        await page.waitForTimeout(1600);
        const slug = (r.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "home").slice(0, 60);
        const file = path.join(out, `${slug}.${vp.name}.${t}.png`);
        await page.screenshot({ path: file, fullPage: flags.has("--full") });
        const hScroll = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
        console.log(file, hScroll ? "HORIZONTAL-SCROLL!" : "", errors.length ? "ERRORS: " + errors.join(" | ") : "");
      }
    }
    await ctx.close();
  }
  await browser.close();
})();
