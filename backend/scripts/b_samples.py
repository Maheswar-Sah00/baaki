"""Render sample messages and PDFs for every language direction into backend/data/samples/ (offline).

Uses a throwaway SQLite database (backend/data/tmp/samples.db) seeded with the demo story, so the app
database is not touched. No Gnani calls; the LLM is off (templates only).

  backend/.venv/Scripts/python backend/scripts/b_samples.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["LLM_PROVIDER"] = "none"

from sqlmodel import create_engine  # noqa: E402

from app import config, db, letter, messages, seed  # noqa: E402
from app.lang import today_ist  # noqa: E402

OUT = config.DATA_DIR / "samples"


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmpdb = config.DATA_DIR / "tmp" / "samples.db"
    tmpdb.parent.mkdir(parents=True, exist_ok=True)
    if tmpdb.exists():
        tmpdb.unlink()
    eng = create_engine(f"sqlite:///{tmpdb.as_posix()}", connect_args={"check_same_thread": False})
    db.set_engine(eng)
    db.init_db(eng)
    with db.session() as s:
        ids = seed.seed(s)
    today = seed.DEMO_TODAY
    texts = {}
    jobs = [("sharma", "lakshmi_to_sharma"), ("rao", "rafiq_to_rao")]
    for key, label in jobs:
        with db.session() as s:
            ctx = messages.load_ctx(s, ids["cases"][key])
        for step in messages.STEPS:
            d = await messages.compose(ctx, step, use_llm=False, today=today)
            en = await messages.compose(ctx, step, lang="en", use_llm=False, today=today)
            wv = await messages.compose(ctx, step, lang=ctx.worker_lang, use_llm=False, today=today)
            texts[f"{label}_{step}"] = {"employer_lang": d.lang, "text": d.text, "speech": d.speech,
                                        "worker_view": wv.text, "english": en.text, "checks_ok": d.checks["ok"]}
            upi = messages.upi_link(ctx.worker.upi_vpa, ctx.worker.name, ctx.balance)
            pdf = letter.render(letter.LetterInput(ctx=ctx, step=step, draft=d, draft_en=en, upi_link=upi, today=today))
            (OUT / f"{step}_{label}_{d.lang}.pdf").write_bytes(pdf)
        pack = letter.render_legal_pack(letter.LetterInput(ctx=ctx, step="legal_pack", today=today))
        (OUT / f"legal_pack_{label}.pdf").write_bytes(pack)
    (OUT / "ladder_texts.json").write_text(json.dumps(texts, ensure_ascii=False, indent=1), encoding="utf-8")
    db.set_engine(None)
    eng.dispose()
    tmpdb.unlink(missing_ok=True)
    print("wrote", sorted(p.name for p in OUT.glob("*.pdf")), "today", today, "(real today", today_ist(), ")")


if __name__ == "__main__":
    asyncio.run(main())
