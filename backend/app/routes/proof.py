"""Noise proof bench (G04+V14): the measured results behind Baaki's headline number.

GET /api/proof                   summary (headline, per condition, misses) + every clip row
GET /api/proof/audio/{clip_id}   the exact audio Prisma heard for that clip (e.g. te01-combined, hi03-clean)

Read-only. Results come from backend/scripts/bench_noisy.py (run once, offline from the web):
backend/data/bench/results.json, falling back to backend/seed_cache/bench/ (committed copy for deploys).
The web never triggers a Gnani call here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config, proof_bench as pb

router = APIRouter(prefix="/api/proof", tags=["proof"])

CLIP_RE = re.compile(r"^[a-z]{2}\d{2}-[a-z0-9]{3,16}$")
MIME = {"ogg": "audio/ogg", "wav": "audio/wav"}

METHOD = [
    "12 short sentences a worker might say, 6 in Telugu and 6 in Hinglish, each with one or two rupee amounts, "
    "spoken by 11 different Gnani Timbre stock voices.",
    "Each clip was made worse on purpose with ffmpeg: a synthetic kitchen (running tap, pressure-cooker whistle, "
    "clattering steel) as loud as the voice, and kitchen noise + an 8 kHz phone line + 12 kbps WhatsApp-style "
    "compression all at once.",
    "Gnani Prisma transcribed every clip with the app's own settings, and Baaki's own number parser read the "
    "amounts. An amount counts only if it comes out exactly right.",
]
CAVEATS = [
    "Stock voices are clearer than a real person, and the kitchen is synthetic. This is a small test, not an "
    "accuracy rate.",
    "Every clip ran once. Nothing was re-run or picked. Any miss is listed here.",
]


def bench_dirs() -> list[Path]:
    return [config.DATA_DIR / "bench", config.SEED_CACHE_DIR / "bench"]


def load_results() -> dict[str, Any] | None:
    for d in bench_dirs():
        p = d / "results.json"
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return None


def _clip_view(r: dict[str, Any]) -> dict[str, Any]:
    cond = pb.CONDITIONS.get(r["condition"], {})
    keep = ("clip_id", "utt_id", "lang", "voice", "condition", "snr_db", "text", "gloss", "expected", "heard",
            "amounts", "hits", "total", "extras", "spans", "match", "word_slips", "transcript", "latency_s",
            "duration_s", "sample_rate", "stt_lang", "stt_language_code", "mode", "model", "error")
    out = {k: r.get(k) for k in keep}
    out["condition_label"] = cond.get("label", r["condition"])
    out["lang_label"] = pb.LANG_LABEL.get(r["lang"], r["lang"])
    out["audio_url"] = f"/api/proof/audio/{r['clip_id']}"
    out["clean_url"] = f"/api/proof/audio/{pb.clip_id(r['utt_id'], 'clean')}"
    return out


@router.get("")
def proof() -> dict[str, Any]:
    res = load_results()
    if not res:
        return {"available": False, "method": METHOD, "caveats": CAVEATS, "summary": None, "clips": []}
    rows = [r for r in res.get("clips", []) if r.get("condition") in pb.CONDITIONS]
    order = {c: i for i, c in enumerate(pb.CONDITION_ORDER)}
    rows.sort(key=lambda r: (r["utt_id"], order.get(r["condition"], 99)))
    calls = res.get("calls") or {}
    runs = calls.get("runs") or []
    return {
        "available": True,
        "generated_at": res.get("updated_at"),
        "run_dates": [x.get("at") for x in runs],
        "model": (res.get("settings") or {}).get("model", "prisma-v3.0"),
        "settings": res.get("settings"),
        "calls": {"tts": calls.get("tts"), "stt": calls.get("stt")},
        "summary": pb.summarize(rows),
        "conditions": [{"id": c, **{k: v for k, v in pb.CONDITIONS[c].items() if k != "ext"}}
                       for c in pb.CONDITION_ORDER],
        "method": METHOD,
        "caveats": CAVEATS,
        "clips": [_clip_view(r) for r in rows],
    }


@router.get("/audio/{clip_id}")
def proof_audio(clip_id: str) -> FileResponse:
    if not CLIP_RE.match(clip_id) or not pb.parse_clip_id(clip_id):
        raise HTTPException(404, {"error": "unknown_clip"})
    for d in bench_dirs():
        base = (d / "audio").resolve()
        for ext, mime in MIME.items():
            p = (base / f"{clip_id}.{ext}").resolve()
            if p.parent == base and p.is_file():
                return FileResponse(p, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(404, {"error": "audio_not_found"})
