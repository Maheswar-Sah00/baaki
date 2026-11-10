"""Build Baaki_Solution_Pitch.pdf (repo root): the one-page solution pitch (same text as PITCH.md), A4.

Run: python docs/architecture/tools/make_pitch_pdf.py
Needs Python Playwright and an installed Edge or Chrome. Prints the page count; it must be 1.

The look is the app's own "pale" palette (web/app/theme-pale.css, docs/DESIGN_SYSTEM.md): paper white, pastel
washes with their readable inks, ink pills and hairlines, no gradients and no glow. Type: Cabinet Grotesk
(embedded from web/app/fonts), Inter and Instrument Serif italic accents (Google Fonts), Noto Sans Telugu.
The phone strip uses real app screens (docs/screens/pitch/*.jpg, frames from the demo footage, synthetic data).
"""
from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "Baaki_Solution_Pitch.pdf"
SCREENS = ROOT / "docs/screens/pitch"
CABINET = base64.b64encode((ROOT / "web/app/fonts/CabinetGrotesk-Variable.woff2").read_bytes()).decode()
MARK = ('<svg viewBox="0 0 512 512" width="46" height="46"><rect width="512" height="512" rx="114" fill="#0e0e0c"/>'
        '<path fill="#fbfaf7" transform="translate(74.77 74.77) scale(0.6762)" d="M80 120a64 64 0 0 1 128 0V170a160 '
        '160 0 0 1 248 134V480L400 432H144a64 64 0 0 1-64-64Z M296 246a58 58 0 1 0 0.01 0Z"/></svg>')

# (file, step caption, who / language)
STEPS = [
    ("1-speak.jpg", "She talks in Telugu. The <b>Baaki Meter</b> counts up: ₹13,000.", "Lakshmi · Telugu"),
    ("2-law.jpg", "Read back slowly. Law check: the sick-day cut was too big, so <b>₹12,692</b>.", "Lakshmi · Telugu"),
    ("3-note.jpg", "A polite voice note in <b>his</b> language, AI label first, checked by Listen-twice.", "To Sharma ji · Hinglish"),
    ("4-employer.jpg", "His page: every line with its rule. He plays the note and taps <b>I've paid</b>.", "Sharma ji · Hinglish"),
    ("5-paisa.jpg", "She confirms it arrived: <b>Paisa aa gaya!</b> Nothing counts until she does.", "Lakshmi · Telugu"),
]


def _img(name: str) -> str:
    return "data:image/jpeg;base64," + base64.b64encode((SCREENS / name).read_bytes()).decode()


HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Baaki: solution pitch</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=Noto+Sans+Telugu:wght@500;700&display=block" rel="stylesheet">
<style>
@font-face { font-family: Cabinet; src: url(data:font/woff2;base64,__CABINET__) format("woff2"); font-weight: 100 900; }
@page { size: A4; margin: 0; }
:root { --paper:#fbfaf7; --surface:#ffffff; --surface2:#f6f4ef; --line:#ebe8e1; --line2:#dcd8cf;
        --ink:#0e0e0c; --text2:#3f3d39; --muted:#6b6862;
        --peach:#fbeadf; --peach-ink:#8a4b22; --butter:#f8f0d6; --butter-ink:#6f5a12;
        --sage:#e3ede0; --sage-ink:#2f5a33; --lilac:#ece6f8; --lilac-ink:#4f3f8c; --rose:#f8e4e8; --rose-ink:#8a3346; }
* { box-sizing:border-box; margin:0; padding:0; }
html, body { width:210mm; height:297mm; }
body { font-family: Inter, "Noto Sans Telugu", sans-serif; color:var(--text2); font-size:8.9pt; line-height:1.42;
       background:var(--paper); position:relative; }
.page { padding:10mm 13mm 0 13mm; }
h1, h2, .num, .big, .statement { font-family: Cabinet, Inter, sans-serif; color:var(--ink); }
.accent { font-family:"Instrument Serif", serif; font-style:italic; font-weight:400; letter-spacing:0; }
.eyebrow { font-size:6.9pt; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }
header { display:flex; align-items:center; gap:12px; }
header h1 { font-size:27pt; font-weight:800; letter-spacing:-0.02em; line-height:1; }
header h1 .te { font-family:"Noto Sans Telugu", sans-serif; font-weight:700; font-size:18pt; color:var(--muted); }
header .sub { font-size:12pt; color:var(--ink); font-weight:500; margin-top:3px; }
header .sub .accent { font-size:14pt; }
header .right { margin-left:auto; text-align:right; }
.tag { color:var(--ink); font-size:12.5pt; line-height:1.1; }
.tag small { display:block; font-family:Inter; font-style:normal; color:var(--muted); font-size:7.8pt; margin-top:2px; }
.pill { display:inline-block; margin-top:6px; padding:4px 11px; border-radius:999px; font-size:7.6pt; font-weight:600;
        color:#fff; background:var(--ink); }
.statement { margin-top:11px; font-size:15pt; font-weight:700; line-height:1.2; letter-spacing:-0.01em; }
.statement .accent { font-size:17pt; }
.stats { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:11px; }
.stat { border-radius:16px; padding:10px 12px 9px; }
.stat.peach { background:var(--peach); } .stat.butter { background:var(--butter); } .stat.sage { background:var(--sage); }
.stat .num { font-size:23pt; font-weight:800; line-height:1; letter-spacing:-0.02em; }
.stat p { margin-top:4px; color:var(--ink); font-weight:500; font-size:8.8pt; line-height:1.28; }
.stat small { display:block; margin-top:4px; font-size:6.9pt; line-height:1.3; }
.stat.peach small { color:var(--peach-ink); } .stat.butter small { color:var(--butter-ink); } .stat.sage small { color:var(--sage-ink); }
.strip-head { display:flex; justify-content:space-between; align-items:baseline; margin-top:12px; }
.strip-head h2 { font-size:12pt; }
.strip { display:grid; grid-template-columns:repeat(5,1fr); gap:7px; margin-top:6px; }
.shot { background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:5px 5px 7px; }
.shot img { display:block; width:100%; height:49mm; object-fit:cover; object-position:center top; border-radius:11px;
            border:1px solid var(--line); }
.shot .cap { display:flex; gap:6px; margin-top:6px; padding:0 2px; font-size:7.4pt; line-height:1.3; color:var(--text2); }
.shot .n { flex:none; width:14px; height:14px; border-radius:50%; background:var(--ink); color:#fff; font-size:6.8pt;
           font-weight:700; text-align:center; line-height:14px; margin-top:1px; }
.shot .who { display:block; margin-top:2px; font-size:6.5pt; color:var(--muted); }
.cols { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:12px; }
h2 { font-size:11.5pt; font-weight:800; margin:0 0 3px; letter-spacing:-0.01em; }
section { margin-bottom:9px; }
b { color:var(--ink); font-weight:600; }
.model { display:grid; grid-template-columns:76px 1fr; gap:8px; padding:5px 0; border-top:1px solid var(--line); }
.model:first-of-type { border-top:none; padding-top:2px; }
.chip { font-size:7.2pt; font-weight:700; border-radius:999px; padding:3px 6px; text-align:center; align-self:start;
        line-height:1.2; }
.chip.p { background:var(--peach); color:var(--peach-ink); }
.chip.t { background:var(--lilac); color:var(--lilac-ink); }
.chip.c { background:var(--surface); color:var(--ink); border:1px solid var(--line2); }
.proof { border-radius:16px; padding:9px 13px 10px; background:var(--surface); border:1px solid var(--line);
         display:grid; grid-template-columns:auto 1fr; gap:4px 12px; align-items:center; }
.proof .big { font-size:27pt; font-weight:800; line-height:1; letter-spacing:-0.02em; }
.proof p { color:var(--ink); line-height:1.3; }
.proof .cav { grid-column:1 / -1; font-size:7.8pt; color:var(--muted); }
.proof .cav .accent { font-size:9.5pt; color:var(--text2); }
.note { color:var(--muted); font-size:7.9pt; }
.law { display:inline-block; padding:1px 7px; border-radius:999px; background:var(--butter); color:var(--butter-ink);
       font-size:7.4pt; font-weight:600; }
footer { position:absolute; left:13mm; right:13mm; bottom:7mm; border-top:1px solid var(--line); padding-top:6px;
         display:flex; justify-content:space-between; gap:10px; font-size:7.3pt; color:var(--muted); white-space:nowrap; }
footer b { color:var(--ink); }
footer a { color:var(--ink); }
</style></head><body>
<div class="page">
<header>
  __MARK__
  <div>
    <h1>Baaki <span class="te">· బాకీ</span></h1>
    <div class="sub">A wage advocate in her <span class="accent">pocket.</span></div>
  </div>
  <div class="right">
    <div class="tag"><span class="accent">"Bolo. Baaki sambhal lega."</span><small>Just speak. Baaki asks.</small></div>
    <div class="pill">Built on Gnani.ai Prisma + Timbre</div>
  </div>
</header>

<div class="statement">Hyderabad's maids and cooks are often owed money they can't calculate, can't put in writing,
and <span class="accent">can't safely ask for</span> in their employer's language.</div>

<div class="stats">
  <div class="stat peach"><div class="num">81%</div><p>of Hyderabad's domestic workers earned below the state's minimum wage</p>
    <small>Montfort Social Institute survey, via Siasat (27 Aug 2025)</small></div>
  <div class="stat butter"><div class="num">6 lakh</div><p>domestic workers in Hyderabad alone</p>
    <small>NGO estimate (Montfort Social Institute), Siasat (16 Jun 2025). Officials say 2 lakh.</small></div>
  <div class="stat sage"><div class="num">61.1%</div><p>literacy among rural women in Telangana, so voice comes first</p>
    <small>PLFS 2023-24, Telangana Today (8 Dec 2024)</small></div>
</div>

<div class="strip-head"><h2>See it <span class="accent">work</span></h2>
  <span class="eyebrow">Real app screens · synthetic data · her Telugu, his Hinglish</span></div>
<div class="strip">__STRIP__</div>

<div class="cols">
<div>
  <section><h2>Who it's for</h2>
  Domestic workers in Hyderabad, mostly women, who speak <b>Telugu or Hinglish</b>, work in 3 to 6 homes with no
  contract, and are paid in cash or UPI. Second user: the <b>employer</b>, who opens the link she shares on WhatsApp.
  No app, no login.</section>

  <section><h2>The solution</h2>
  <b>She speaks, confirms and presses Send.</b> Baaki does the rest: it adds up what she is owed, checks it against
  the law <span class="law">Code on Wages 2019 · Telangana G.O.Ms.No.6</span>, reads it back to her, and asks the
  employer for her in a polite, <b>AI-disclosed voice note in his language</b>. It keeps hash-chained proof and
  follows up until she confirms the money arrived.</section>

  <section><h2>Why it matters, and what's <span class="accent">next</span></h2>
  Baaki never asks for more than the law supports, so the request is hard to wave away, and she can ask without
  risking the job. <b>Next:</b> the milkman's bill and chit money (in the app as "other dues"), a basic-phone line
  on Gnani's voice agents, and more of Gnani's languages.
  <div class="note" style="margin-top:3px">Not legal advice: it points to the Labour Department, NALSA 15100 and
    India Labourline.</div></section>
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
  <div class="note" style="margin-top:2px">Every rupee comes from our own Telugu and Hindi number parsers, never
    from a language model.</div></section>

  <section><h2>Proof</h2>
  <div class="proof"><div class="big">34 / 34</div>
  <p><b>rupee amounts heard exactly</b> across 24 noisy clips: a kitchen as loud as the voice; kitchen, phone line
    and WhatsApp compression at once.</p>
  <div class="cav"><span class="accent">A small test, not an accuracy rate:</span> stock Gnani voices, a synthetic
    kitchen, 12 sentences, run once.</div>
  </div></section>
</div>
</div>
</div>
<footer><span><b>Repo:</b> <a href="https://github.com/Maheswar-Sah00/baaki">github.com/Maheswar-Sah00/baaki</a></span>
<span><b>Demo video:</b> linked at the top of the repo README</span>
<span>Gnani.ai Great Indian AI Internship Challenge</span></footer>
</body></html>"""


def strip_html() -> str:
    return "".join(
        f'<div class="shot"><img src="{_img(f)}" alt=""><div class="cap"><span class="n">{i}</span>'
        f'<span>{cap}<span class="who">{who}</span></span></div></div>'
        for i, (f, cap, who) in enumerate(STEPS, 1))


async def main() -> None:
    html = HTML.replace("__CABINET__", CABINET).replace("__MARK__", MARK).replace("__STRIP__", strip_html())
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
