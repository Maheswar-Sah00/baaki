"""Live check of the employer side with the real Gnani key (Agent B). Spends at most 8 Gnani calls,
one at a time, one attempt each (no automatic retries), and stops before going over.

  1. Polite voice note, Lakshmi -> Sharma ji, Hinglish, stock voice (one Timbre call per sentence).
  2. Employer reply round trip: a synthetic Hinglish reply (Timbre, male voice) -> POST /api/e/{token}/reply
     -> Prisma (hi-IN,en-IN, codemix) -> translation into Telugu -> Timbre te-IN.
Outputs go to backend/data/samples/. Synthetic people only. Keys are never printed.

  backend/.venv/Scripts/python backend/scripts/b_live_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import create_engine  # noqa: E402

from app import audio, config, db, gnani, seed  # noqa: E402

# Agent B was allowed 8 live calls. Run 1 (9 Nov) spent 7: 5 Timbre calls for the polite note (now in the TTS
# cache, so the note re-renders for free), 1 Timbre call for the synthetic employer reply below, and 1 Prisma call
# whose response was lost to a decoding bug in this script's transport (fixed). So BUDGET = 1 is left.
BUDGET = 1
REPLY_CLIP = config.DATA_DIR / "samples" / "employer_reply_input_sharma_hi-en.ogg"   # Timbre Avinash, hi-en, made in run 1
REPLY_CLIP_TEXT = "लक्ष्मी को बोलो, मैं शनिवार को बारह हज़ार रुपये दे दूँगा, बाकी अगले महीने।"
OUT = config.DATA_DIR / "samples"
CALLS: list[str] = []


class CountingTransport(httpx.AsyncBaseTransport):
    """A fresh real transport per request (the client closes its transport after each call)."""

    async def handle_async_request(self, request):
        if len(CALLS) >= BUDGET:  # a TransportError, so the app reports it as audio_error and carries on
            raise httpx.ConnectError("live-check Gnani call budget reached; call not sent")
        CALLS.append(request.url.path)
        async with httpx.AsyncHTTPTransport() as t:
            resp = await t.handle_async_request(request)
            content = await resp.aread()
            headers = [(k, v) for k, v in resp.headers.items() if k.lower() not in ("content-encoding", "content-length")]
            return httpx.Response(resp.status_code, headers=headers, content=content)


def main() -> None:
    if not config.gnani_key():
        raise SystemExit("GNANI_API_KEY is not set")
    OUT.mkdir(parents=True, exist_ok=True)
    gnani._default = gnani.GnaniClient(transport=CountingTransport(), max_attempts=1, backoff_s=0.0)
    tmpdb = config.DATA_DIR / "tmp" / "live_check.db"
    tmpdb.parent.mkdir(parents=True, exist_ok=True)
    tmpdb.unlink(missing_ok=True)
    eng = create_engine(f"sqlite:///{tmpdb.as_posix()}", connect_args={"check_same_thread": False})
    db.set_engine(eng)
    db.init_db(eng)
    with db.session() as s:
        ids = seed.seed(s)
    report: dict = {"seed_totals": ids["totals"]}
    from app.main import app

    with TestClient(app) as c:
        # 1. polite voice note (stock voice)
        r = c.post(f"/api/cases/{ids['cases']['sharma']}/messages/polite", json={"use_llm": False, "voice": "stock"})
        b = r.json()
        report["polite"] = {"status": r.status_code, "text": b.get("text"), "speech": b.get("speech"),
                            "audio": b.get("audio"), "audio_error": b.get("audio_error"), "calls_so_far": len(CALLS)}
        if b.get("audio_url"):
            data = c.get(b["audio_url"]).content
            (OUT / "voice_note_polite_lakshmi_to_sharma_hi-en.ogg").write_bytes(data)
            report["polite"]["tags"] = audio.read_tags(data)
            report["polite"]["probe"] = audio.probe(data, "ogg").as_dict()
        print("polite:", r.status_code, "calls", len(CALLS), flush=True)

        # 2. synthetic employer reply (Hinglish, male stock voice), then the reply round trip
        if len(CALLS) < BUDGET and REPLY_CLIP.exists():
            reply_text = REPLY_CLIP_TEXT
            emp = REPLY_CLIP.read_bytes()
            r = c.post(f"/api/e/{ids['employer_tokens']['sharma']}/reply",
                       files={"audio": ("reply.ogg", emp, "audio/ogg")})
            b = r.json()
            report["reply"] = {"status": r.status_code, "sent_text": reply_text, "transcript": b.get("transcript"),
                               "stt": b.get("stt"), "amounts": b.get("amounts"), "translation": b.get("translation"),
                               "audio": b.get("audio"), "audio_error": b.get("audio_error"), "calls_so_far": len(CALLS)}
            if b.get("audio", {}) and b["audio"].get("url"):
                data = c.get(b["audio"]["url"]).content
                (OUT / "employer_reply_translated_for_lakshmi_te-IN.ogg").write_bytes(data)
                report["reply"]["probe"] = audio.probe(data, "ogg").as_dict()
            print("reply:", r.status_code, "calls", len(CALLS), flush=True)
        else:
            report["reply"] = "skipped: not enough budget left"
    report["gnani_calls"] = CALLS
    (OUT / "live_check_result.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    db.set_engine(None)
    eng.dispose()
    tmpdb.unlink(missing_ok=True)
    print("total gnani calls:", len(CALLS))


if __name__ == "__main__":
    main()
