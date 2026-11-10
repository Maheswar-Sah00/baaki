"""Build Baaki_Solution_Pitch.pdf (repo root): the one-page solution pitch (same text as PITCH.md), A4.

Run: python docs/architecture/tools/make_pitch_pdf.py
Needs Python Playwright and an installed Edge or Chrome. Cabinet Grotesk is embedded from web/app/fonts;
Inter and Noto Sans Telugu come from Google Fonts. Prints the page count; it must be 1.
"""
from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Baaki_Solution_Pitch.pdf"
CABINET = base64.b64encode((ROOT / "web/app/fonts/CabinetGrotesk-Variable.woff2").read_bytes()).decode()
MARK = ('<svg viewBox="0 0 512 512" width="44" height="44"><rect width="512" height="512" rx="114" fill="#0e0e0c"/>'
        '<path fill="#fbfaf7" transform="translate(74.77 74.77) scale(0.6762)" d="M80 120a64 64 0 0 1 128 0V170a160 '
        '160 0 0 1 248 134V480L400 432H144a64 64 0 0 1-64-64Z M296 246a58 58 0 1 0 0.01 0Z"/></svg>')

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Telugu:wght@500;700&display=block" rel="stylesheet">
<style>
@font-face { font-family: Cabinet; src: url(data:font/woff2;base64,__CABINET__) format("woff2"); font-weight: 100 900; }
@page { size: A4; margin: 0; }
:root { --ink:#0e0e0c; --text2:#3f3d39; --muted:#6b6862; --line:#ebe8e1; --paper:#fbfaf7;
        --o:#FE914B; --v:#9F73F4; --grad:linear-gradient(90deg,#FE914B,#9F73F4);
        --peach:#fbeadf; --lilac:#ece6f8; --sage:#e3ede0; --butter:#f8f0d6; }
* { box-sizing:border-box; margin:0; padding:0; }
html, body { width:210mm; height:297mm; }
body { font-family: Inter, "Noto Sans Telugu", sans-serif; color:var(--text2); font-size:9.45pt; line-height:1.46;
       background:#fff; position:relative; }
.bar { height:5px; background:var(--grad); }
.page { padding:11mm 14mm 0 14mm; }
h1, h2, .num, .big { font-family: Cabinet, Inter, sans-serif; color:var(--ink); }
header { display:flex; align-items:center; gap:12px; }
header h1 { font-size:27pt; font-weight:800; letter-spacing:-0.01em; line-height:1; }
header h1 .te { font-family:"Noto Sans Telugu", sans-serif; font-weight:700; font-size:19pt; }
header .sub { font-size:11pt; color:var(--ink); font-weight:600; margin-top:3px; }
header .right { margin-left:auto; text-align:right; }
.tag { font-style:italic; color:var(--ink); font-size:10pt; }
.pill { display:inline-block; margin-top:5px; padding:3px 9px; border-radius:999px; font-size:7.6pt; font-weight:600;
        color:#fff; background:var(--grad); }
.statement { margin-top:13px; font-family:Cabinet, Inter, sans-serif; font-size:14.8pt; font-weight:700; color:var(--ink);
             line-height:1.22; }
.statement span { background:var(--grad) left bottom / 100% 3px no-repeat; padding-bottom:1px; }
.stats { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:14px; }
.stat { border:1px solid var(--line); border-radius:12px; padding:11px 12px; background:var(--paper); }
.stat .num { font-size:24pt; font-weight:800; line-height:1.05; color:var(--ink); }
.stat .num::after { content:""; display:block; width:34px; height:4px; border-radius:2px; background:var(--grad); margin-top:4px; }
.stat p { margin-top:5px; color:var(--ink); font-weight:500; font-size:9.2pt; line-height:1.3; }
.stat small { display:block; margin-top:4px; color:var(--muted); font-size:7.4pt; line-height:1.3; }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:14px; }
h2 { font-size:12pt; font-weight:800; margin:0 0 4px; display:flex; align-items:center; gap:6px; }
h2::before { content:""; width:14px; height:4px; border-radius:2px; background:var(--grad); }
section { margin-bottom:11px; }
b { color:var(--ink); font-weight:600; }
ol.steps { list-style:none; counter-reset:s; }
ol.steps li { counter-increment:s; position:relative; padding-left:24px; margin-bottom:5px; }
ol.steps li::before { content:counter(s); position:absolute; left:0; top:0; width:16px; height:16px; border-radius:50%;
                      background:var(--ink); color:#fff; font-size:7.4pt; font-weight:700; text-align:center; line-height:16px; }
.model { display:grid; grid-template-columns:84px 1fr; gap:8px; padding:5px 0; border-top:1px solid var(--line); }
.model:first-of-type { border-top:none; }
.chip { font-size:7.4pt; font-weight:700; color:var(--ink); border-radius:7px; padding:3px 6px; text-align:center;
        align-self:start; }
.chip.p { background:var(--peach); border:1px solid var(--o); }
.chip.t { background:var(--lilac); border:1px solid var(--v); }
.chip.c { background:#fff; border:1px dashed var(--v); }
.proof { border-radius:12px; padding:10px 14px; background:linear-gradient(135deg,#fbeadf,#ece6f8); }
.proof .big { font-size:28pt; font-weight:800; line-height:1; color:var(--ink); }
.proof .big span { font-size:10.5pt; font-weight:700; }
.proof p { margin-top:4px; color:var(--ink); }
.proof .cav { margin-top:5px; font-size:8.3pt; color:var(--text2); font-style:italic; }
.note { color:var(--muted); font-size:8.3pt; }
footer { position:absolute; left:14mm; right:14mm; bottom:7mm; border-top:1px solid var(--line); padding-top:6px;
         display:flex; justify-content:space-between; font-size:8.2pt; color:var(--muted); white-space:nowrap; }
footer b { color:var(--ink); }
</style></head><body>
<div class="bar"></div>
<div class="page">
<header>
  __MARK__
  <div>
    <h1>Baaki <span class="te">· బాకీ</span></h1>
    <div class="sub">A wage advocate in her pocket.</div>
  </div>
  <div class="right">
    <div class="tag">"Bolo. Baaki sambhal lega."<br><span style="font-style:normal;color:var(--muted);font-size:8pt">Just speak. Baaki asks.</span></div>
    <div class="pill">Built on Gnani.ai Prisma + Timbre</div>
  </div>
</header>

<div class="statement">Hyderabad's maids and cooks are often owed money they can't calculate, can't put in writing,
and <span>can't safely ask for in their employer's language.</span></div>

<div class="stats">
  <div class="stat"><div class="num">81%</div><p>of Hyderabad's domestic workers earned below the state's minimum wage</p>
    <small>Montfort Social Institute survey, via Siasat (27 Aug 2025)</small></div>
  <div class="stat"><div class="num">6 lakh</div><p>domestic workers in Hyderabad alone</p>
    <small>Union estimate, Siasat (16 Jun 2025). Officials say 2 lakh.</small></div>
  <div class="stat"><div class="num">61.1%</div><p>literacy among rural women in Telangana, so voice comes first</p>
    <small>PLFS 2023-24, Telangana Today (8 Dec 2024)</small></div>
</div>

<div class="cols">
<div>
  <section><h2>Who it's for</h2>
  Domestic workers in Hyderabad, mostly women, who speak <b>Telugu or Hinglish</b>, work in 3 to 6 homes with no
  contract, and are paid in cash or UPI. Second user: the <b>employer</b>, who opens the link she shares on WhatsApp.
  No app, no login.</section>

  <section><h2>The solution</h2>
  <b>She speaks, confirms and presses Send.</b> Baaki does the rest: it adds up what she is owed, checks it against
  the law (Code on Wages 2019; Telangana G.O.Ms.No.6), reads it back to her, and asks the employer for her in a
  polite, <b>AI-disclosed voice note in his language</b>. It keeps hash-chained proof and follows up until she
  confirms the money arrived.</section>

  <section><h2>Demo in 5 steps <span class="note" style="font-family:Inter;font-weight:400">(synthetic data)</span></h2>
  <ol class="steps">
    <li>Lakshmi talks in Telugu. The <b>Baaki Meter</b> counts up as she speaks: ₹13,000.</li>
    <li>Baaki reads it back slowly in Telugu. She says <b>"Haan, sahi hai"</b>. Nothing is saved before that.</li>
    <li>Law check: s.20(2) allows ₹308 of the ₹1,000 sick-day cut, so her baaki is <b>₹12,692</b>.</li>
    <li>A polite Hinglish voice note, AI disclosure first, checked by <b>Listen-twice</b>. She shares it on WhatsApp.</li>
    <li>Sharma ji's page plays it and opens UPI. He taps "I've paid". She confirms it arrived:
        <b>"Paisa aa gaya!"</b></li>
  </ol></section>
</div>
<div>
  <section><h2>How Gnani's models power it</h2>
  <div class="model"><div class="chip p">Prisma v3.0<br>STT</div><div>Hears her (<b>te-IN, hi-IN, en-IN</b> in one
    request, codemix: no language picker), his replies and her spoken consent. <b>Listen-twice:</b> re-hears every
    voice note before she sends it, to check each amount and the AI label.</div></div>
  <div class="model"><div class="chip t">Timbre v3.0<br>TTS</div><div>Speaks the read-back (&lt;slow&gt;,
    &lt;pauses&gt;), the voice notes in Hinglish or Telugu, and "Paisa aa gaya!" (&lt;excited&gt;).</div></div>
  <div class="model"><div class="chip c">Voice Clone</div><div>Opt-in, with spoken consent: the note can be in
    her own voice.</div></div>
  <div class="note" style="margin-top:3px">Every rupee comes from our own Telugu and Hindi number parsers, never
    from a language model.</div></section>

  <section><h2>Proof</h2>
  <div class="proof"><div class="big">34 / 34</div>
  <p><b>rupee amounts heard exactly</b> across 24 noisy clips: a kitchen as loud as the voice; kitchen, phone line and WhatsApp compression at once.</p>
  <div class="cav">Stock Gnani voices, a synthetic kitchen, 12 sentences, run once: a small test, not an accuracy rate.</div>
  </div></section>

  <section><h2>Why it matters, and what's next</h2>
  Baaki never asks for more than the law supports, so the request is hard to wave away, and she can ask without
  risking the job. <b>Next:</b> the milkman's bill and chit money (in the app as "other dues"), a
  basic-phone line on Gnani's voice agents, and more of Gnani's languages.
  <div class="note" style="margin-top:3px">Not legal advice: it points to the Labour Department, NALSA 15100 and
    India Labourline.</div></section>
</div>
</div>
</div>
<footer><span><b>Repo:</b> github.com/Maheswar-Sah00/baaki</span><span><b>Demo video:</b> in the repo README</span>
<span>Gnani.ai Great Indian AI Internship Challenge</span></footer>
</body></html>"""


async def main() -> None:
    html = HTML.replace("__CABINET__", CABINET).replace("__MARK__", MARK)
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge")
        except Exception:
            browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        await page.pdf(path=str(OUT), format="A4", print_background=True, prefer_css_page_size=True)
        await browser.close()
    try:
        from pypdf import PdfReader
        print(f"{OUT.name}: {len(PdfReader(str(OUT)).pages)} page(s)")
    except ImportError:
        print(f"{OUT.name} written (pypdf not installed: page count not checked)")


if __name__ == "__main__":
    asyncio.run(main())
