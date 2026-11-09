// Generates the link-preview images (1200x630) in public/og with a headless browser, so the real
// brand fonts render: Cabinet Grotesk (local woff2), Instrument Serif italic and Inter (Google Fonts).
//   node scripts/make-og.mjs                      (BAAKI_URL=http://localhost:3013 for the proof card)
//
//   og/baaki-og.png   default for every route (lib/site.ts OG_IMAGE). Generic on purpose: no names
//                     and no amounts, so it is safe for every route, including /e/{token}.
//   og/check-og.png   Fair Pay Check (/check)
//   og/proof-og.png   Noise proof (/proof): the headline number, read live from GET /api/proof.
//                     Skipped (old file kept) when the API is not reachable.
//
// Look: the pale painted sky (public/sky.webp), a Cabinet headline with an Instrument Serif italic
// line, ink pill, hairline cards. Colours are the `pale` palette from app/theme-pale.css.
// Playwright comes from B:/Projects/appwrite (like scripts/shots.cjs); the PNGs are committed, so
// other machines never need to run this.
import { createRequire } from "node:module";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(WEB, "public", "og");
mkdirSync(OUT, { recursive: true });
const require = createRequire(import.meta.url);
let chromium;
for (const p of ["playwright", "B:/Projects/appwrite/node_modules/playwright"]) {
  try {
    ({ chromium } = require(p));
    break;
  } catch {
    /* try the next */
  }
}
if (!chromium) throw new Error("Playwright not found (npm i -D playwright, or keep B:/Projects/appwrite)");

const b64 = (f) => readFileSync(f).toString("base64");
const SKY = `data:image/webp;base64,${b64(path.join(WEB, "public", "sky.webp"))}`;
const CABINET = `data:font/woff2;base64,${b64(path.join(WEB, "app", "fonts", "CabinetGrotesk-Variable.woff2"))}`;
const MARK =
  "M80 120a64 64 0 0 1 128 0V170a160 160 0 0 1 248 134V480L400 432H144a64 64 0 0 1-64-64Z M296 246a58 58 0 1 0 0.01 0Z";

const INK = "#0e0e0c";
const css = `
@font-face { font-family: "Cabinet"; src: url(${CABINET}) format("woff2"); font-weight: 100 900; }
* { box-sizing: border-box; margin: 0; }
html, body { width: 1200px; height: 630px; overflow: hidden; }
body { font-family: Inter, "Segoe UI", sans-serif; color: ${INK}; background: #fbfaf7; }
.card { position: relative; width: 1200px; height: 630px; padding: 56px 72px; display: flex; flex-direction: column;
  background: url(${SKY}) center 30% / cover no-repeat; }
.card::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgb(251 250 247 / 0) 40%, rgb(251 250 247 / 0.86) 100%); }
.card > * { position: relative; z-index: 1; }
.top { display: flex; align-items: center; justify-content: space-between; }
.logo { display: flex; align-items: center; gap: 12px; }
.logo svg { width: 38px; height: 38px; }
.word { font-family: Cabinet; font-weight: 700; font-size: 38px; letter-spacing: -0.045em; line-height: 1; }
.te { font-family: "Nirmala UI", "Noto Sans Telugu", sans-serif; font-size: 19px; font-weight: 500; color: #4a4843; margin-left: 4px; }
.pill { font-weight: 600; font-size: 19px; padding: 12px 22px; border-radius: 999px; background: ${INK}; color: #fff; }
.pill.ghost { background: rgb(255 255 255 / 0.72); color: ${INK}; border: 1px solid rgb(14 14 12 / 0.08); }
h1 { font-family: Cabinet; font-weight: 700; font-size: 104px; line-height: 0.96; letter-spacing: -0.045em; }
h1 em { display: block; font-family: "Instrument Serif", Georgia, serif; font-style: italic; font-weight: 400; letter-spacing: -0.02em; font-size: 1.06em; }
.sub { margin-top: 26px; font-size: 27px; line-height: 1.38; color: #3f3d39; max-width: 820px; }
.mid { margin-top: auto; }
.row { margin-top: 34px; display: flex; gap: 12px; align-items: center; }
.chip { font-size: 18px; font-weight: 600; padding: 10px 18px; border-radius: 999px; background: rgb(255 255 255 / 0.8); border: 1px solid rgb(14 14 12 / 0.07); color: #3f3d39; }
.big { font-family: Cabinet; font-weight: 700; font-size: 250px; line-height: 0.8; letter-spacing: -0.06em; }
.big span { color: #a8a49b; }
.center { align-items: center; text-align: center; }
.center .top { width: 100%; }
`;

const logo = `<div class="logo"><svg viewBox="56 56 424 424"><path fill="${INK}" d="${MARK}"/></svg><span class="word">Baaki</span><span class="te" lang="te">బాకీ</span></div>`;

const cards = {
  "baaki-og.png": `
  <div class="card">
    <div class="top">${logo}<span class="pill">Telugu · Hinglish</span></div>
    <div class="mid">
      <h1>Money still owed?<em>Just say it.</em></h1>
      <p class="sub">Baaki works out what a domestic worker is owed and speaks to the employer for her, in their language.</p>
      <div class="row"><span class="chip">Voice first</span><span class="chip">Read back before Send</span><span class="chip">Telangana minimum wage</span></div>
    </div>
  </div>`,
  "check-og.png": `
  <div class="card">
    <div class="top">${logo}<span class="pill ghost">Fair Pay Check</span></div>
    <div class="mid">
      <h1>Am I paying my<em>house help fairly?</em></h1>
      <p class="sub">A 30-second check against Telangana's minimum wage (G.O.Ms.No.6, Hyderabad). Nothing you enter is saved.</p>
    </div>
  </div>`,
};

async function proofCard() {
  const base = process.env.BAAKI_URL || "http://localhost:3013";
  try {
    const res = await fetch(`${base}/api/proof`, { signal: AbortSignal.timeout(6000) });
    const data = await res.json();
    const h = data?.summary?.headline;
    if (!h) return null;
    return `
  <div class="card center">
    <div class="top">${logo}<span class="pill ghost">Noise proof</span></div>
    <div class="mid" style="margin-top:auto;margin-bottom:auto;padding-top:20px">
      <div class="big">${h.exact}<span>/${h.amounts}</span></div>
      <h1 style="font-size:64px;margin-top:22px">rupee amounts heard <em style="display:inline;font-size:1.08em">exactly</em></h1>
      <p class="sub" style="margin:18px auto 0;max-width:900px">${h.clips} noisy clips of Telugu and Hinglish: a loud kitchen, a phone line, WhatsApp compression.</p>
    </div>
  </div>`;
  } catch {
    return null;
  }
}

const proof = await proofCard();
if (proof) cards["proof-og.png"] = proof;
else console.log("skipped proof-og.png (API not reachable)");

let browser;
try {
  browser = await chromium.launch({ channel: "msedge" });
} catch {
  browser = await chromium.launch();
}
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
for (const [name, body] of Object.entries(cards)) {
  const html = `<!doctype html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&display=block" rel="stylesheet">
<style>${css}</style></head><body>${body}</body></html>`;
  await page.setContent(html, { waitUntil: "networkidle" }).catch(() => page.setContent(html));
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(OUT, name), type: "png" });
  console.log("wrote public/og/" + name);
}
await browser.close();
if (!existsSync(path.join(OUT, "baaki-og.png"))) process.exitCode = 1;
