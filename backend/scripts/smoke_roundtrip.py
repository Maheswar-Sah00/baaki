"""Real-key smoke test: Timbre TTS -> Prisma STT round trip through the Baaki API routes.

For each sample: POST /api/tts (synthetic sentence) -> save the OGG -> POST /api/stt with it -> print
transcript and latency. Runs in-process (FastAPI TestClient, lifespan included) unless --base points
at a running server. Calls are sequential (Gnani allows 1 active request). Cost per sample: 1 TTS +
1 STT; TTS is cached in backend/data/tts_cache, so a re-run spends only STT credits.
Outputs go to backend/data/smoke/ (gitignored). The API key is never printed.

  backend/.venv/Scripts/python.exe backend/scripts/smoke_roundtrip.py            # Telugu + Hinglish
  backend/.venv/Scripts/python.exe backend/scripts/smoke_roundtrip.py --only te  # Telugu only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import audio, config  # noqa: E402

OUT = BACKEND / "data" / "smoke"

# Synthetic sentences (fictional; no real person).
SAMPLES = {
    "te": {"tts_lang": "te-IN", "stt_lang": "te",
           "text": "అమ్మగారు, నాకు మూడు నెలల జీతం ఇంకా రాలేదు. మొత్తం పన్నెండు వేల రూపాయలు బాకీ ఉంది."},
    "hinglish": {"tts_lang": "hi-en", "stt_lang": "hinglish",
                 "text": "Madam, मेरी तीन महीने की salary अभी तक नहीं मिली. Total बारह हज़ार रुपये बाकी हैं."},
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(SAMPLES), help="run one sample only")
    ap.add_argument("--base", help="URL of a running backend, e.g. http://127.0.0.1:8000 (default: in-process)")
    args = ap.parse_args()
    if not config.gnani_key():
        print("GNANI_API_KEY is not set in .env")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    if args.base:
        import httpx
        client_cm = httpx.Client(base_url=args.base, timeout=180)
    else:
        from fastapi.testclient import TestClient
        from app.main import app
        client_cm = TestClient(app)

    results, ok = {}, True
    with client_cm as c:
        print("health:", c.get("/api/health").json())
        for name, s in SAMPLES.items():
            if args.only and name != args.only:
                continue
            res: dict = {"text": s["text"], "tts_lang": s["tts_lang"], "stt_lang": s["stt_lang"]}
            t0 = time.perf_counter()
            r = c.post("/api/tts", json={"text": s["text"], "lang": s["tts_lang"]})
            res["tts"] = {"status": r.status_code, "latency_s": round(time.perf_counter() - t0, 2),
                          "cache": r.headers.get("x-tts-cache"), "voice": r.headers.get("x-tts-voice"),
                          "duration_s": r.headers.get("x-duration-s")}
            if r.status_code != 200:
                res["tts"]["error"] = r.text[:400]
                results[name], ok = res, False
                print(name, "TTS failed:", json.dumps(res["tts"], ensure_ascii=False))
                continue
            ogg = OUT / f"{name}_tts.ogg"
            ogg.write_bytes(r.content)
            res["tts"]["probe"] = audio.probe(r.content, "ogg").as_dict()

            t0 = time.perf_counter()
            r = c.post("/api/stt", files={"audio": (ogg.name, r.content, "audio/ogg")},
                       data={"lang": s["stt_lang"], "mode": "transcribe"})
            res["stt"] = {"status": r.status_code, "latency_s": round(time.perf_counter() - t0, 2)}
            if r.status_code == 200:
                body = r.json()
                res["stt"].update(transcript=body["transcript"], detected=body["detected_language_code"],
                                  language_code=body["language_code"], model=body["model"])
            else:
                res["stt"]["error"] = r.text[:400]
                ok = False
            results[name] = res
            print(f"\n[{name}] TTS {res['tts']['status']} {res['tts']['latency_s']} s "
                  f"(cache {res['tts']['cache']}, voice {res['tts']['voice']}, {res['tts']['duration_s']} s audio)")
            print(f"[{name}] sent:  {s['text']}")
            print(f"[{name}] STT {res['stt']['status']} {res['stt']['latency_s']} s "
                  f"({res['stt'].get('language_code')}, detected {res['stt'].get('detected')})")
            print(f"[{name}] heard: {res['stt'].get('transcript', res['stt'].get('error'))}")

    (OUT / "smoke_result.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), "utf-8")
    print(f"\nwrote {OUT / 'smoke_result.json'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
