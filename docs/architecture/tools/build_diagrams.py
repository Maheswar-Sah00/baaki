"""Build the README diagrams as real Excalidraw files.

For each diagram this script writes three files to docs/architecture/:
  <name>.excalidraw   the Excalidraw scene (open it at https://excalidraw.com: menu -> Open)
  <name>.svg          exported by Excalidraw's own exportToSvg (Excalifont embedded as base64, white background)
  <name>.png          the SVG rendered at 2x

How it works: the layouts below are Excalidraw "element skeletons" (rectangles, ellipses, text, arrows bound to
their boxes). A headless browser loads @excalidraw/excalidraw 0.18.0 from esm.sh, turns the skeletons into
elements with convertToExcalidrawElements (it measures the text), then calls exportToSvg and serializeAsJSON.

Run (needs Python Playwright and an installed Edge or Chrome; internet access for the CDN):
  python docs/architecture/tools/build_diagrams.py            # all diagrams
  python docs/architecture/tools/build_diagrams.py proof-chain
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1]
EXCALIDRAW = "https://esm.sh/@excalidraw/excalidraw@0.18.0?deps=react@18.3.1,react-dom@18.3.1"
ASSETS = "https://unpkg.com/@excalidraw/excalidraw@0.18.0/dist/prod/"

# Palette: the app's pale tokens (web/app/theme-pale.css) with Gnani orange -> violet accents.
INK, TEXT2, MUTED = "#0e0e0c", "#3f3d39", "#6b6862"
ORANGE, VIOLET = "#FE914B", "#9F73F4"
PEACH, LILAC, SKY, SAGE, BUTTER, ROSE, PAPER, WHITE = (
    "#fbeadf", "#ece6f8", "#e3ecf8", "#e3ede0", "#f8f0d6", "#f8e4e8", "#f6f4ef", "#ffffff")
FONT = 5  # Excalifont


class D:
    """A diagram: a list of skeleton elements plus the boxes arrows can bind to."""

    def __init__(self, title: str, subtitle: str):
        self.els: list[dict] = []
        self.boxes: dict[str, tuple[float, float, float, float]] = {}
        self.text(40, 28, title, 34, INK)
        self.text(40, 80, subtitle, 19, MUTED)
        self.els.append(dict(type="line", x=42, y=122, points=[[0, 0], [86, 0]], strokeColor=ORANGE, strokeWidth=4,
                             roughness=1))
        self.els.append(dict(type="line", x=136, y=122, points=[[0, 0], [86, 0]], strokeColor=VIOLET, strokeWidth=4,
                             roughness=1))

    def text(self, x, y, text, size=17, color=TEXT2, group=None):
        e = dict(type="text", x=x, y=y, text=text, fontSize=size, fontFamily=FONT, strokeColor=color, roughness=1)
        if group:
            e["groupIds"] = [group]
        self.els.append(e)

    def card(self, id, x, y, w, h, title, body=None, fill=WHITE, stroke=INK, dashed=False, tsize=21, bsize=17,
             tcolor=INK):
        g = f"g_{id}"
        self.els.append(dict(type="rectangle", id=id, x=x, y=y, width=w, height=h, backgroundColor=fill,
                             fillStyle="solid", strokeColor=stroke, strokeWidth=2, roughness=1,
                             roundness={"type": 3}, strokeStyle="dashed" if dashed else "solid", groupIds=[g]))
        self.boxes[id] = (x, y, w, h)
        self.text(x + 18, y + 14, title, tsize, tcolor, g)
        if body:
            self.text(x + 18, y + 14 + tsize * 1.25 + 10, body, bsize, TEXT2, g)

    def node(self, id, x, y, w, h, label, fill=WHITE, stroke=INK, shape="ellipse", size=20):
        self.els.append(dict(type=shape, id=id, x=x, y=y, width=w, height=h, backgroundColor=fill, fillStyle="solid",
                             strokeColor=stroke, strokeWidth=2, roughness=1,
                             **({"roundness": {"type": 3}} if shape == "rectangle" else {}),
                             label=dict(text=label, fontSize=size, fontFamily=FONT, strokeColor=INK)))
        self.boxes[id] = (x, y, w, h)

    def frame(self, x, y, w, h, label):
        self.els.append(dict(type="rectangle", x=x, y=y, width=w, height=h, backgroundColor="transparent",
                             strokeColor=MUTED, strokeWidth=1, strokeStyle="dashed", roughness=1,
                             roundness={"type": 3}))
        self.text(x + 16, y + 10, label, 16, MUTED)

    def _edge(self, id, side, t=0.5):
        x, y, w, h = self.boxes[id]
        return {"r": (x + w, y + h * t), "l": (x, y + h * t), "t": (x + w * t, y), "b": (x + w * t, y + h)}[side]

    def arrow(self, a, b, sa="r", sb="l", ta=0.5, tb=0.5, via=None, label=None, color=INK, dashed=False,
              width=2, bind=True):
        """Arrow from box a (side sa at fraction ta) to box b (side sb at tb), optionally through `via` points."""
        GAP = 6
        sx, sy = self._edge(a, sa, ta)
        ex, ey = self._edge(b, sb, tb)
        off = {"r": (GAP, 0), "l": (-GAP, 0), "t": (0, -GAP), "b": (0, GAP)}
        sx, sy = sx + off[sa][0], sy + off[sa][1]
        ex, ey = ex + off[sb][0], ey + off[sb][1]
        pts = [(sx, sy), *(via or []), (ex, ey)]
        e = dict(type="arrow", x=sx, y=sy, points=[[px - sx, py - sy] for px, py in pts], strokeColor=color,
                 strokeWidth=width, roughness=1, endArrowhead="arrow",
                 strokeStyle="dashed" if dashed else "solid")
        if bind:
            e["start"], e["end"] = {"id": a}, {"id": b}
        if label:
            e["label"] = dict(text=label, fontSize=16, fontFamily=FONT, strokeColor=MUTED)
        self.els.append(e)


# --------------------------------------------------------------------------- 1. system architecture
def system_architecture() -> D:
    d = D("Baaki: system architecture",
          "One container runs the web app and the API. Every Gnani call goes through one client, gnani.py.")
    d.card("her", 40, 170, 270, 170, "Her phone",
           "Installable PWA\n(Next.js 16, React 19)\nvoice-first screens,\nTelugu or Hinglish", PEACH, ORANGE)
    d.card("emp", 40, 560, 270, 150, "Employer's phone", "Opens her link:\n/e/{token}\nno app, no login", LILAC,
           VIOLET)
    d.arrow("her", "emp", "b", "t", label="she shares the link\n(WhatsApp, Web Share)", dashed=True, color=MUTED)

    d.frame(360, 140, 600, 790, "One Docker container (Render or Fly.io) · persistent disk at /data")
    d.card("next", 390, 180, 540, 110, "Next.js server (next start)",
           "Serves the pages and proxies /api/* to FastAPI.\nAPI keys never reach the phone.", SKY)
    d.card("api", 390, 340, 540, 420, "FastAPI backend (Python 3.12)", None, WHITE, ORANGE, tsize=22)
    d.card("routes", 410, 395, 245, 105, "routes/*", "cases · e · verify · inbox\nhisaab · raise · exit · ...",
           PAPER, MUTED, tsize=19, bsize=16)
    d.card("gn", 665, 395, 245, 105, "gnani.py", "one request at a time,\nretry 429, breaker", PEACH, ORANGE,
           tsize=19, bsize=16)
    d.card("lang", 410, 515, 245, 105, "app/lang + wages.py", "Telugu / Hindi number\nparsers: every rupee",
           PAPER, MUTED, tsize=19, bsize=16)
    d.card("llm", 665, 515, 245, 105, "llm.py", "structure, translation;\nnever an amount", PAPER, MUTED,
           tsize=19, bsize=16)
    d.card("pdf", 410, 635, 245, 105, "letter.py + pdf.py", "bilingual PDFs\n(fpdf2 + HarfBuzz)", PAPER, MUTED,
           tsize=19, bsize=16)
    d.card("cache", 665, 635, 245, 105, "tts_cache.py", "sha256 audio cache +\ncommitted seed_cache", PAPER,
           MUTED, tsize=19, bsize=16)
    d.card("db", 390, 800, 255, 105, "SQLite (SQLModel)", "cases, payments,\nthe diary hash chain", BUTTER,
           MUTED, tsize=19, bsize=16)
    d.card("disk", 675, 800, 255, 105, "Disk /data", "voice notes, PDFs,\nmedia, TTS cache", BUTTER, MUTED,
           tsize=19, bsize=16)

    d.card("prisma", 1020, 340, 320, 120, "Gnani Prisma v3.0 STT", "POST /stt/v3 (REST)\nclips under 28 s, codemix",
           PEACH, ORANGE)
    d.card("timbre", 1020, 490, 320, 120, "Gnani Timbre v3.0 TTS",
           "POST /api/v1/tts/inference\n(REST), audio tags", LILAC, VIOLET)
    d.card("vc", 1020, 640, 320, 120, "Gnani Voice Clone", "vachana-vc-v1, opt-in;\noff on the public deploy",
           WHITE, VIOLET, dashed=True)
    d.card("groq", 1020, 790, 320, 120, "Groq LLM", "openai/gpt-oss-20b\n(Gemini backup, opt-in)", SAGE, MUTED)

    d.arrow("her", "next", "r", "l", ta=0.3, tb=0.4)
    d.arrow("emp", "next", "r", "l", ta=0.3, tb=0.8, via=[(336, 605), (336, 268)])
    d.arrow("next", "api", "b", "t")
    d.text(316, 192, "HTTPS", 14, MUTED)
    d.text(278, 614, "HTTPS", 14, MUTED)
    d.text(672, 304, "/api/*", 15, MUTED)
    d.arrow("gn", "prisma", "r", "l", ta=0.3, tb=0.45)
    d.arrow("gn", "timbre", "r", "l", ta=0.6, tb=0.45)
    d.arrow("gn", "vc", "r", "l", ta=0.85, tb=0.45, dashed=True)
    d.arrow("llm", "groq", "r", "l", ta=0.6, tb=0.45)
    d.arrow("api", "db", "b", "t", ta=0.23)
    d.arrow("api", "disk", "b", "t", ta=0.75)
    return d


# --------------------------------------------------------------------------- 2. worker journey
def worker_journey() -> D:
    d = D("How it works: from her words to “Paisa aa gaya!”",
          "Lakshmi speaks Telugu. Sharma ji speaks Hinglish. Synthetic demo story.")
    W, H, GAP, X0 = 285, 150, 40, 40
    rows = [
        ("1 · She tells it, in Telugu", [
            ("s1", "1 · Speak", "Taps the mic and talks:\n“Mūḍu nelalu jītam\nivvalēdu...”", "her"),
            ("s2", "2 · Baaki Meter", "Counts up while she\ntalks: ₹4,000 ...\n₹13,000", "baaki"),
            ("s3", "3 · Read-back", "Timbre reads it back\nslowly, in Telugu.\nNothing is saved yet.", "baaki"),
            ("s4", "4 · “Haan, sahi hai”", "She confirms with\none tap. Only now is\nthe case saved.", "her")]),
        ("2 · Baaki checks the law and asks, in his language", [
            ("s5", "5 · Law check", "s.20(2) allows ₹308 of\nthe ₹1,000 sick-day cut.\nHer baaki: ₹12,692", "baaki"),
            ("s6", "6 · Voice note", "Polite, Firm, Formal.\nIn Hinglish, with the\nAI disclosure first.", "baaki"),
            ("s7", "7 · Listen-twice", "Prisma re-hears it:\nevery amount, the AI\nlabel. Warns only.", "baaki"),
            ("s8", "8 · She shares it", "From her own phone,\non WhatsApp. She\npresses Send.", "her")]),
        ("3 · He pays, she confirms", [
            ("s9", "9 · Employer page", "Plays the note, shows\nthe itemised ₹12,692,\nopens UPI.", "emp"),
            ("s10", "10 · “I've paid”", "Or pay in parts, or\nreply by voice.\nIt is only a claim.", "emp"),
            ("s11", "11 · She confirms", "“Did it arrive?”\nOnly her yes records\nthe money.", "her"),
            ("s12", "12 · Paisa aa gaya!", "Timbre, <excited>,\nin Telugu. Fair\nEmployer badge.", "done")]),
    ]
    style = {"her": (PEACH, ORANGE), "baaki": (WHITE, INK), "emp": (LILAC, VIOLET), "done": (SAGE, "#2e7a46")}
    y = 175
    prev_last = None
    for label, cards in rows:
        d.text(X0 + 44, y - 42, label, 21, MUTED)
        for i, (cid, title, body, who) in enumerate(cards):
            fill, stroke = style[who]
            d.card(cid, X0 + i * (W + GAP), y, W, H, title, body, fill, stroke, tsize=21, bsize=17)
            if i:
                d.arrow(cards[i - 1][0], cid)
        if prev_last:
            px, py, pw, ph = d.boxes[prev_last]
            first = cards[0][0]
            fx, fy, fw, fh = d.boxes[first]
            mid = py + ph + 22
            d.arrow(prev_last, first, "b", "t", tb=0.07, via=[(px + pw / 2, mid), (fx + fw * 0.07, mid)], color=MUTED)
        prev_last = cards[-1][0]
        y += H + 115
    ly = y - 60
    for i, (name, who) in enumerate([("Lakshmi does it", "her"), ("Baaki does it", "baaki"),
                                     ("Sharma ji does it", "emp"), ("Settled", "done")]):
        fill, stroke = style[who]
        x = X0 + i * 250
        d.els.append(dict(type="rectangle", x=x, y=ly, width=34, height=26, backgroundColor=fill, fillStyle="solid",
                          strokeColor=stroke, strokeWidth=2, roughness=1, roundness={"type": 3}))
        d.text(x + 46, ly + 1, name, 18, TEXT2)
    return d


# --------------------------------------------------------------------------- 3. Gnani voice pipeline
def gnani_voice_pipeline() -> D:
    d = D("Where Gnani's models are called",
          "Prisma hears. Timbre speaks. Then Prisma checks what Timbre said, before she sends it.")
    LX, CX, RX, W = 40, 480, 920, 380
    d.text(LX, 150, "Audio that Prisma hears", 20, MUTED)
    d.text(RX, 150, "What Baaki does with it", 20, MUTED)
    d.card("l1", LX, 190, W, 140, "Her story (live meter)",
           "hooks/useListen.ts → /api/cases/listen\nstt_service.py: te-IN,hi-IN,en-IN\nre-sent every 4.5 s while she talks",
           PEACH, ORANGE, tsize=20, bsize=16)
    d.card("l2", LX, 355, W, 115, "His replies and corrections",
           "routes/employer.py (/reply)\nroutes/inbox.py, routes/hisaab.py", PEACH, ORANGE, tsize=20, bsize=16)
    d.card("l3", LX, 495, W, 115, "Spoken consent, Fair Pay Check",
           "consent_flow.py: word-by-word match\nroutes/check.py: 3 a day per visitor", PEACH, ORANGE, tsize=20,
           bsize=16)
    d.card("l4", LX, 650, W, 140, "Listen-twice",
           "verify_guard.py re-hears the finished\nnote: every amount, the AI label.\nCached per audio sha256. Warns only.",
           WHITE, ORANGE, tsize=20, bsize=16)

    d.card("prisma", CX, 190, W, 150, "Prisma v3.0 STT",
           "POST /stt/v3 (REST)\ncodemix for two or more languages\n(transcribe dropped a spoken amount)",
           PEACH, ORANGE, tsize=24, bsize=16)
    d.card("gn", CX, 385, W, 130, "gnani.py: the one client",
           "1 active request (global lock)\nretries only 429, breaker on 401/402\ndaily budget on the public deploy",
           PAPER, MUTED, tsize=20, bsize=16)
    d.card("timbre", CX, 560, W, 150, "Timbre v3.0 TTS",
           "POST /api/v1/tts/inference (REST)\nKalpana (te-IN), Shivani (hi-en)\n<slow> <pauses> <excited>",
           LILAC, VIOLET, tsize=24, bsize=16)
    d.card("cache", CX, 755, W, 120, "tts_cache.py",
           "sha256(voice|lang|text) on disk, plus the\ncommitted seed_cache: never paid twice", PAPER, MUTED,
           tsize=20, bsize=16)

    d.card("r1", RX, 190, W, 150, "Words → rupees",
           "app/lang parsers + meter.py turn\nnumber words into ₹ (no LLM).\nThe LLM only labels what each is.",
           WHITE, INK, tsize=20, bsize=16)
    d.text(RX, 520, "What Timbre says", 20, MUTED)
    d.card("r2", RX, 560, W, 95, "Read-back to her", "readback.py: amounts as words,\n<slow>, <pauses>", LILAC,
           VIOLET, tsize=20, bsize=16)
    d.card("r3", RX, 675, W, 140, "Voice note for him",
           "voice_note.py: AI disclosure first,\none call per sentence, loudness\nnormalised, Ogg/Opus + AI metadata",
           LILAC, VIOLET, tsize=20, bsize=16)
    d.card("r4", RX, 835, W, 95, "“Paisa aa gaya!”", "ledger.py, <excited>, only after\nshe confirms",
           LILAC, VIOLET, tsize=20, bsize=16)

    for lid in ("l1", "l2", "l3", "l4"):
        d.arrow(lid, "prisma", "r", "l", tb={"l1": 0.3, "l2": 0.5, "l3": 0.7, "l4": 0.9}[lid], color=ORANGE)
    d.arrow("prisma", "r1", "r", "l")
    d.arrow("gn", "prisma", "t", "b", dashed=True, color=MUTED)
    d.arrow("gn", "timbre", "b", "t", dashed=True, color=MUTED)
    d.arrow("cache", "timbre", "t", "b", label="cache miss only", color=MUTED)
    d.arrow("timbre", "r2", "r", "l", ta=0.25, color=VIOLET)
    d.arrow("timbre", "r3", "r", "l", ta=0.6, color=VIOLET)
    d.arrow("timbre", "r4", "r", "l", ta=0.9, color=VIOLET)
    x3, y3, w3, h3 = d.boxes["r3"]
    x4, y4, w4, h4 = d.boxes["l4"]
    d.arrow("r3", "l4", "r", "b", via=[(x3 + w3 + 30, y3 + h3 / 2), (x3 + w3 + 30, 965), (x4 + w4 / 2, 965)],
            color=ORANGE, width=3)
    d.text(x4 + w4 / 2 + 24, 932, "Listen-twice: the exact audio she will send goes back to Prisma", 17, MUTED)
    return d


# --------------------------------------------------------------------------- 4. two-language bridge
def two_language_bridge() -> D:
    d = D("The two-language bridge",
          "Each side speaks, hears and reads its own language. Amounts are checked by code at every crossing.")
    LX, CX, RX, W = 40, 480, 920, 380
    d.node("p_her", LX + 65, 150, 250, 90, "Lakshmi\nspeaks Telugu", PEACH, ORANGE)
    d.node("p_baaki", CX + 65, 150, 250, 90, "Baaki", WHITE, INK, size=24)
    d.node("p_emp", RX + 65, 150, 250, 90, "Sharma ji\nspeaks Hinglish", LILAC, VIOLET)

    d.card("a1", LX, 290, W, 135, "She says",
           "“Mūḍu nelalu jītam ivvalēdu,\nnelaku nālugu vēlu...”",
           PEACH, ORANGE)
    d.card("a2", CX, 290, W, 135, "Prisma → parsers → law",
           "te-IN,hi-IN,en-IN, codemix.\n₹12,692, read back to her\nin Telugu before anything is sent")
    d.card("a3", RX, 290, W, 135, "He hears",
           "“यह एक AI वॉइस संदेश है...”\nthen the amount, politely,\nin a Timbre voice",
           LILAC, VIOLET)
    d.arrow("a1", "a2")
    d.arrow("a2", "a3")

    d.card("b1", LX, 470, W, 115, "She reads", "the same message in Telugu,\nbefore she presses Send", PEACH, ORANGE)
    d.card("b2", CX, 470, W, 115, "One message, two languages",
           "messages.compose(): his language\nto send, hers to read", PAPER, MUTED)
    d.card("b3", RX, 470, W, 115, "He reads", "an itemised card; the Formal\nletter is in Hindi and English",
           LILAC, VIOLET)
    d.arrow("b2", "b1", "l", "r", dashed=True, color=MUTED)
    d.arrow("b2", "b3", "r", "l", dashed=True, color=MUTED)

    d.card("c3", RX, 630, W, 135, "He replies",
           "“Shanivaar ko baarah hazaar\nde dunga, baaki agle mahine”\n(his page, or a WhatsApp note)",
           LILAC, VIOLET)
    d.card("c2", CX, 630, W, 135, "Prisma → translate.py → Timbre",
           "hi-IN,en-IN, codemix. The LLM\ntranslates; app.lang checks that\nevery ₹ still matches")
    d.card("c1", LX, 630, W, 135, "She hears",
           "his reply, spoken in Telugu.\nFrom a WhatsApp note, Promise\nKeeper tracks “by Saturday”",
           PEACH, ORANGE)
    d.arrow("c3", "c2", "l", "r")
    d.arrow("c2", "c1", "l", "r")

    d.card("rev", LX, 810, RX + W - LX, 85, "It works the other way too",
           "Rafiq speaks Hinglish and Rao garu hears Telugu (₹14,000 in the demo). Same code, languages swapped.",
           BUTTER, MUTED, tsize=20, bsize=17)
    return d


# --------------------------------------------------------------------------- 5. proof chain
def proof_chain() -> D:
    d = D("The proof diary: a SHA-256 hash chain",
          "Every diary entry carries the hash of the one before it. Change one word and the chain shows where.")
    W, GAP, X0, Y = 262, 70, 40, 175
    entries = [
        ("e1", "Entry 1 · checkin", "“Aaj Sharma ji ke ghar,\ndo ghante”", "(none)", "4a1e9c..."),
        ("e2", "Entry 2 · absence", "“2 days sick, cut\n₹1,000”", "4a1e9c...", "b7d03f..."),
        ("e3", "Entry 3 · evidence", "His WhatsApp note:\n“Shanivaar ko de dunga”", "b7d03f...",
         "0c93a2..."),
        ("e4", "Entry 4 · consent", "Voice consent given\n(spoken, Prisma match)", "0c93a2...", "e518d7..."),
    ]
    for i, (eid, title, text, prev, h) in enumerate(entries):
        body = f"{text}\n\ntime: 10 Nov, 08:1{i} UTC\naudio: sha256 only\nprev_hash: {prev}\nhash: {h}"
        d.card(eid, X0 + i * (W + GAP), Y, W, 255, title, body, PEACH if i != 2 else LILAC,
               ORANGE if i != 2 else VIOLET, tsize=21, bsize=17)
        if i:
            d.arrow(entries[i - 1][0], eid, ta=0.66, tb=0.66, width=3, color=ORANGE)
    d.text(X0, Y + 268, "Each arrow: the next entry stores this entry's hash as its prev_hash. Hash values are illustrative.", 16, MUTED)

    d.card("f", X0, 525, 4 * W + 3 * GAP, 95, "hash = SHA-256( prev_hash | canonical JSON of the entry )",
           "routes/cases.py: entry_hash(), add_diary_entry(), verify_chain()    ·    the Dues log uses the same scheme (dues_core.py)",
           WHITE, INK, tsize=23, bsize=17)
    BW = (4 * W + 3 * GAP - 2 * 40) / 3
    d.card("x1", X0, 680, BW, 160, "Change one word...",
           "...and that entry's hash no\nlonger matches. The check\nnames the entry where it broke.", ROSE,
           "#b73a2e")
    d.card("x2", X0 + BW + 40, 680, BW, 160, "Letter annex",
           "letter.py prints each entry: time,\ntext, the first 16 characters of\nits hash, and the chain check.", SKY,
           MUTED)
    d.card("x3", X0 + 2 * (BW + 40), 680, BW, 160, "Why it matters",
           "Electronic records in court need\na certificate under BSA s.63. The\nchain shows nothing was edited.",
           BUTTER, MUTED)
    for x, t in (("x1", 0.17), ("x2", 0.5), ("x3", 0.83)):
        d.arrow("f", x, "b", "t", ta=t, color=MUTED)
    d.text(X0, 860, "Also chained into her diary: inbox evidence cards and voice consent or withdrawal. Not legal advice.",
           17, MUTED)
    return d


DIAGRAMS = {
    "system-architecture": system_architecture,
    "worker-journey": worker_journey,
    "gnani-voice-pipeline": gnani_voice_pipeline,
    "two-language-bridge": two_language_bridge,
    "proof-chain": proof_chain,
}

PAGE = f"""<!doctype html><html><head><meta charset="utf-8"></head><body>
<script>window.EXCALIDRAW_ASSET_PATH = "{ASSETS}";</script>
<script type="module">
import * as EX from "{EXCALIDRAW}";
window.build = async (skel) => {{
  const elements = EX.convertToExcalidrawElements(skel, {{ regenerateIds: false }});
  const appState = {{ exportBackground: true, viewBackgroundColor: "#ffffff", exportWithDarkMode: false }};
  const svg = await EX.exportToSvg({{ elements, appState, files: {{}}, exportPadding: 36 }});
  const json = EX.serializeAsJSON(elements, {{ viewBackgroundColor: "#ffffff" }}, {{}}, "local");
  return {{ svg: svg.outerHTML, json }};
}};
window.READY = true;
</script></body></html>"""


async def main(names: list[str]) -> None:
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge")
        except Exception:
            browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page()
        await page.set_content(PAGE)
        await page.wait_for_function("window.READY === true", timeout=120_000)
        # warm-up: the first export loads Excalifont, so later text is measured with the right font
        await page.evaluate("(s) => window.build(s)", [dict(type="text", x=0, y=0, text="Baaki ₹ warm-up",
                                                            fontSize=20, fontFamily=FONT)])
        shot = await browser.new_page(device_scale_factor=2)
        for name in names:
            d = DIAGRAMS[name]()
            r = await page.evaluate("(s) => window.build(s)", d.els)
            (OUT / f"{name}.excalidraw").write_text(r["json"], encoding="utf-8")
            (OUT / f"{name}.svg").write_text(r["svg"], encoding="utf-8")
            await shot.set_content(f'<html><body style="margin:0;background:#fff">{r["svg"]}</body></html>')
            await shot.evaluate("document.fonts.ready")
            await shot.locator("svg").first.screenshot(path=str(OUT / f"{name}.png"))
            print(f"{name}: {len(d.els)} skeleton elements, svg {len(r['svg']) // 1024} KB")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(DIAGRAMS)))
