"""Warm the TTS cache for the demo story, and optionally export it to backend/seed_cache (committed).

Runs against a RUNNING backend (scripts/start-demo.ps1), so the clips land in the server's cache:
  1. POST /api/demo/reset
  2. Sharma ji's Polite note (Hinglish voice note, Lakshmi -> Sharma ji): 5 sentences, one Timbre call each
  3. the read-back for the filming story (Telugu, "Ammagaru, three months at 4,000, 1,000 cut for two days
     of fever", home = Sharma ji), through POST /api/cases like the app does
  4. "I've paid" on the employer page (a claim) -> Lakshmi confirms it -> the Telugu "Paisa aa gaya" alert
  5. (--rao) Rafiq -> Rao garu's Polite note in Telugu (the reverse demo)
  6. (--live-consent) Rafiq's Hinglish voice-consent sentence (/voice/consent), 1 Timbre call the first time
  7. POST /api/demo/reset again, so filming starts clean
Every clip already in the cache costs nothing. DATE-DEPENDENT: the Polite note's last sentence says the
reply-by date (today + 7 days), so it is new every day: run this on filming morning (1 Timbre call).
--export copies the date-independent clips into backend/seed_cache/tts and writes
backend/seed_cache/demo_manifest.json, so a cold start spends no credits on them.

Takes backend/data/gnani_live.lock (one active Gnani request per account) for the whole run.

  backend\\.venv\\Scripts\\python backend\\scripts\\warm_demo.py [--base http://127.0.0.1:8020] [--export] [--rao]
      [--live-consent]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import config, tts_cache  # noqa: E402
from app.messages import fmt_date, tts_lang  # noqa: E402

LOCK = config.DATA_DIR / "gnani_live.lock"
MANIFEST = config.SEED_CACHE_DIR / "demo_manifest.json"
# What Prisma heard from the synthetic filming clip (bench te01 + te04), 9 Nov 2026.
STORY_TE = ("అమ్మగారు మూడు నెలలుగా నెలకు నాలుగు వేలు జీతం ఇవ్వలేదు. "
            "రెండు రోజులు జ్వరం వచ్చిందని వెయ్యి రూపాయలు కోత పెట్టారు.")


def take_lock(wait_s: int = 180) -> None:
    deadline = time.time() + wait_s
    while True:
        try:
            with open(LOCK, "x", encoding="utf-8") as f:
                f.write("warm_demo.py")
            return
        except FileExistsError:
            if time.time() > deadline:
                sys.exit(f"{LOCK} is held by another run; try again later (delete it if no run is active).")
            print("waiting for the Gnani lock ...")
            time.sleep(20)


def clip(text: str, lang: str, purpose: str, date_dependent: bool = False) -> dict:
    text = text.strip()
    voice = tts_cache.default_voice(lang)
    return {"key": tts_cache.cache_key(text, lang, voice), "lang": lang, "voice": voice, "purpose": purpose,
            "date_dependent": date_dependent, "text": text}


def note_clips(step: dict, purpose: str) -> list[dict]:
    """One clip per spoken sentence of a ladder step; the sentence with the reply-by date is date-dependent."""
    lang = tts_lang(step["language"])
    reply_by = dt.date.fromisoformat(step["reply_by"]) if step.get("reply_by") else None
    marks = {fmt_date(reply_by, step["language"], year=False), fmt_date(reply_by, step["language"])} if reply_by else set()
    return [clip(s, lang, purpose, any(m and m in s for m in marks)) for s in step.get("speech") or []]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8020", help="running backend")
    ap.add_argument("--export", action="store_true", help="copy date-independent clips to backend/seed_cache")
    ap.add_argument("--rao", action="store_true", help="also warm Rafiq -> Rao garu (Telugu Polite note)")
    ap.add_argument("--live-consent", action="store_true",
                    help="also warm Rafiq's Hinglish voice-consent prompt (a live Timbre call if not cached)")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    # In public mode (BAAKI_PUBLIC=1) the demo resets need the admin token; it is read from .env, never printed.
    headers = {"X-Admin-Token": config.admin_token()} if getattr(config, "admin_token", None) and config.admin_token() else {}
    c = httpx.Client(base_url=base, timeout=300, headers=headers)
    try:
        before = c.get("/health").json()["gnani_calls"]
    except httpx.HTTPError:
        sys.exit(f"Backend not reachable at {base}. Start it first: scripts\\start-demo.ps1")

    take_lock()
    clips: list[dict] = []
    problems: list[str] = []
    try:
        seed = c.post("/api/demo/reset").raise_for_status().json()
        lakshmi, sharma = seed["workers"]["lakshmi"], seed["employers"]["sharma"]

        # Polite note, Lakshmi -> Sharma ji (Hinglish)
        step = c.post(f"/api/cases/{seed['cases']['sharma']}/messages/polite",
                      json={"use_llm": True, "audio": True, "pdf": False}).raise_for_status().json()
        if step.get("audio_error"):
            problems.append(f"polite audio: {step['audio_error']}")
        clips += note_clips(step, "polite: Lakshmi -> Sharma ji")
        print(f"polite (Sharma ji): {len(step.get('speech') or [])} sentences, reply by {step.get('reply_by')}")

        # Read-back for the filming story (same path as the app: create the case, then /readback)
        case = c.post("/api/cases", json={"worker_id": lakshmi, "employer_id": sharma, "lang": "te",
                                          "transcript": STORY_TE, "use_llm": True}).raise_for_status().json()
        rb = c.post(f"/api/cases/{case['id']}/readback", json={}).raise_for_status().json()
        if rb.get("tts_error"):
            problems.append(f"read-back audio: {rb['tts_error']}")
        clips.append(clip(rb["text"], rb["lang"], "read-back: filming story (Telugu, home Sharma ji)"))
        print(f"read-back: total {case.get('total_due')}, cached={rb.get('cached')}")

        # "I've paid" is a claim; her confirmation records it and makes "Paisa aa gaya" (Telugu, for Lakshmi)
        paid = c.post(f"/api/e/{seed['employer_tokens']['sharma']}/pay", json={}).raise_for_status().json()
        alert = paid.get("alert")
        if alert is None and (paid.get("claim") or {}).get("id"):
            dec = c.post(f"/api/hisaab/{paid['claim']['id']}/decide",
                         json={"decision": "accept"}).raise_for_status().json()
            alert = dec.get("alert")
        if not alert:
            raise SystemExit("no 'Paisa aa gaya' alert came back from I've paid -> confirm; check the backend log")
        if alert.get("audio_error"):
            problems.append(f"paid alert audio: {alert['audio_error']}")
        clips.append(clip(alert["speech"], tts_lang(alert["language"]), "paid alert: Sharma ji paid in full"))
        print("paid alert:", alert["text"])

        if args.rao:
            step = c.post(f"/api/cases/{seed['cases']['rao']}/messages/polite",
                          json={"use_llm": True, "audio": True, "pdf": False}).raise_for_status().json()
            if step.get("audio_error"):
                problems.append(f"rao polite audio: {step['audio_error']}")
            clips += note_clips(step, "polite: Rafiq -> Rao garu")
            print(f"polite (Rao garu): {len(step.get('speech') or [])} sentences")

        if args.live_consent:
            # Rafiq speaks Hinglish, so no lang: the prompt uses his own language. Name-dependent, not date-dependent.
            cp = c.post("/api/consent/prompt", json={"worker_id": seed["workers"]["rafiq"]}).raise_for_status().json()
            if cp.get("tts_error"):
                problems.append(f"consent prompt audio: {cp['tts_error']}")
            clips.append(clip(cp["speech"], cp["tts_lang"], "consent prompt: Rafiq (Hinglish)"))
            print(f"consent prompt (Rafiq, {cp.get('lang')}): cached={cp.get('cached')}")

        c.post("/api/demo/reset").raise_for_status()
    finally:
        LOCK.unlink(missing_ok=True)

    after = c.get("/health").json()["gnani_calls"]
    used = {k: after[k] - before.get(k, 0) for k in after if after[k] != before.get(k, 0)}
    print(f"Gnani calls this run: {used or 'none (all cached)'}")

    missing = [x for x in clips if not tts_cache.lookup(x["key"])]
    for x in missing:
        problems.append(f"not in cache: {x['purpose']}: {x['text'][:60]}")
    if args.export:
        exported = []
        for x in clips:
            if x["date_dependent"]:
                print(f"skip (date-dependent): {x['text'][:70]}")
                continue
            if tts_cache.export_to_seed(x["key"]):
                exported.append({k: x[k] for k in ("key", "lang", "voice", "purpose", "text")})
        old = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {"clips": []}
        keep = {e["key"]: e for e in old.get("clips", [])}
        keep.update({e["key"]: e for e in exported})
        MANIFEST.write_text(json.dumps({
            "about": "TTS clips the demo story needs, pre-rendered so a cold start spends no Gnani credits. "
                     "Not here: the Polite note's reply-by sentence (changes daily; run scripts/warm-demo.ps1 on "
                     "filming morning) and the Listen-twice check (Prisma STT, cached per message).",
            "updated": dt.date.today().isoformat(),
            "clips": sorted(keep.values(), key=lambda e: e["purpose"])}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"exported {len(exported)} clips to {config.SEED_CACHE_DIR / 'tts'}")
    if problems:
        print("PROBLEMS:\n  " + "\n  ".join(problems))
        return 1
    print("Demo cache is warm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
