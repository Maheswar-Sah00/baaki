"""Noise proof bench (G04+V14): how many rupee amounts does Baaki hear exactly in bad audio?

  backend/.venv/Scripts/python backend/scripts/bench_noisy.py --dry-run
  backend/.venv/Scripts/python backend/scripts/bench_noisy.py --conditions clean,combined
  backend/.venv/Scripts/python backend/scripts/bench_noisy.py --conditions kitchen_0db,phone,whatsapp --utts te01,te02,hi01,hi02

1. Clean clips: 12 synthetic worker sentences (6 Telugu, 6 Hinglish) in Timbre stock voices, made
   through app.tts_cache, so a repeat run spends nothing.
2. Degraded copies with ffmpeg only (app.proof_bench): kitchen at 5 and 0 dB SNR, 8 kHz phone line,
   WhatsApp-style 12 kbps Opus, and all combined. Audio goes to backend/data/bench/audio/.
3. Each selected (clip, condition) goes through app.stt_service.transcribe_upload with the app's
   production settings (lang preset te / hinglish, default mode -> codemix for these multi-language
   presets, domain topic + keyterms on), then app.lang.amounts, scored exact per amount.
4. backend/data/bench/results.json holds every row, the summary and a call ledger. Finished rows are
   skipped (resume). Totals are capped at --max-tts / --max-stt across runs.

Gnani: takes backend/data/gnani_live.lock for the whole run (one active request per account), one attempt
per call (no retries), and stops at once on HTTP 429/402 (or 401/403), saving progress.
Synthetic data only. Keys are never printed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import audio, config, gnani, proof_bench as pb, tts_cache  # noqa: E402
from app.stt_service import transcribe_upload  # noqa: E402

BENCH = config.DATA_DIR / "bench"
AUDIO_DIR = BENCH / "audio"
RESULTS = BENCH / "results.json"
LOCK = config.DATA_DIR / "gnani_live.lock"
STOP_STATUSES = {401, 402, 403, 429}
# encoded sample rate per condition (Opus files always report 48 kHz on decode)
RATE = {"kitchen_5db": 16000, "kitchen_0db": 16000, "phone": 8000, "whatsapp": 16000, "combined": 16000}
STT_LANG = {"te": "te", "hinglish": "hinglish"}  # the presets cases.py sends for these languages


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> dict:
    if RESULTS.exists():
        return json.loads(RESULTS.read_text(encoding="utf-8"))
    return {"version": 1, "calls": {"tts": 0, "stt": 0, "runs": []}, "clips": []}


def save(res: dict) -> None:
    BENCH.mkdir(parents=True, exist_ok=True)
    res["summary"] = pb.summarize(res["clips"])
    res["updated_at"] = now()
    tmp = RESULTS.with_suffix(".json.part")
    tmp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(RESULTS)


def clean_entry(u: dict) -> Path | None:
    key = tts_cache.cache_key(u["text"], u["tts_lang"], u["voice"])
    return tts_cache.lookup(key)


def audio_path(cid: str) -> Path | None:
    for ext in ("ogg", "wav"):
        p = AUDIO_DIR / f"{cid}.{ext}"
        if p.exists():
            return p
    return None


def make_variants(u: dict, clean: Path, seed: int) -> dict[str, dict]:
    """Write every condition's audio (free, offline). Returns {condition: {path, snr}}."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    meta_p = AUDIO_DIR / f"{u['id']}.meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    data = clean.read_bytes()
    for c in pb.CONDITION_ORDER:
        cid = pb.clip_id(u["id"], c)
        if audio_path(cid) and c in meta:
            continue
        b, ext, snr = pb.degrade(data, "ogg", c, seed=seed)
        (AUDIO_DIR / f"{cid}.{ext}").write_bytes(b)
        info = audio.probe(b, ext)
        meta[c] = {"file": f"{cid}.{ext}", "snr_db": snr, "duration_s": info.duration_s,
                   "codec": info.codec, "bytes": len(b),
                   "sample_rate": RATE.get(c, info.sample_rate)}
    meta_p.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def take_lock(max_wait_s: float) -> None:
    t0 = time.time()
    while True:
        try:
            with open(LOCK, "x", encoding="utf-8") as f:
                f.write(f"bench_noisy pid={os.getpid()} at={now()}\n")
            print(f"lock taken: {LOCK}", flush=True)
            return
        except FileExistsError:
            if time.time() - t0 > max_wait_s:
                raise SystemExit(f"Gnani lock still held after {max_wait_s:.0f} s: {LOCK}")
            print("Gnani lock busy, retrying in 20 s", flush=True)
            time.sleep(20)


def release_lock() -> None:
    try:
        LOCK.unlink()
        print("lock released", flush=True)
    except FileNotFoundError:
        pass


def export_seed(res: dict) -> int:
    """Copy results.json and the audio of every scored clip (plus its clean original) into
    backend/seed_cache/bench/, which is committed, so a deployed backend serves /api/proof too."""
    import shutil

    dst = config.SEED_CACHE_DIR / "bench"
    (dst / "audio").mkdir(parents=True, exist_ok=True)
    names = set()
    for r in res["clips"]:
        names.add(pb.clip_id(r["utt_id"], r["condition"]))
        names.add(pb.clip_id(r["utt_id"], "clean"))
    n = 0
    for cid in sorted(names):
        p = audio_path(cid)
        if p:
            shutil.copyfile(p, dst / "audio" / p.name)
            n += 1
    shutil.copyfile(RESULTS, dst / "results.json")
    print(f"exported results.json + {n} audio files to {dst}", flush=True)
    return 0


async def run(args) -> int:
    res = load()
    conds = [c.strip() for c in args.conditions.split(",") if c.strip()]
    bad = [c for c in conds if c not in pb.CONDITIONS]
    if bad:
        raise SystemExit(f"unknown condition(s) {bad}; choose from {pb.CONDITION_ORDER}")
    utts = [pb.CORPUS_BY_ID[x] for x in args.utts.split(",")] if args.utts else pb.CORPUS
    res["corpus"] = pb.CORPUS
    res["conditions"] = pb.CONDITIONS
    res["settings"] = {"model": "prisma-v3.0", "stt_lang": {"te": "te-IN,en-IN", "hinglish": "hi-IN,en-IN"},
                       "mode": "codemix (transcribe is switched to codemix for multi-language presets)",
                       "context": "domain topic + keyterms (STT_CONTEXT default on)",
                       "tts": "timbre-v3.0 stock voices via tts_cache", "parser": "app.lang.amounts.extract_amounts"}
    if args.export_seed:
        return export_seed(res)
    if args.rescore:  # re-score saved transcripts offline (parser or scoring changed): no calls
        for r in res["clips"]:
            if r.get("transcript") is not None and not r.get("error"):
                r.update(pb.score(r["expected"], r["transcript"], r["lang"], said=r["text"]))
        save(res)
        print("rescored", len(res["clips"]), "rows; headline:", (res["summary"]["headline"] or {}).get("text"))
        return 0
    done = {r["clip_id"] for r in res["clips"] if r.get("transcript") is not None and not r.get("error")}

    # sanity: the parser reads every source sentence correctly (else the test itself is wrong)
    for u in pb.CORPUS:
        s = pb.score(u["expected"], u["text"], u["lang"])
        if not s["match"]:
            raise SystemExit(f"{u['id']}: parser reads the source text as {s['heard']}, expected {u['expected']}")

    need_tts = [u for u in utts if not clean_entry(u)]
    jobs = [(u, c) for u in utts for c in conds if pb.clip_id(u["id"], c) not in done]
    if args.limit is not None:
        jobs = jobs[: args.limit]
    tts_left = args.max_tts - res["calls"]["tts"]
    stt_left = args.max_stt - res["calls"]["stt"]
    print(f"plan: {len(need_tts)} TTS (left {tts_left}), {len(jobs)} STT (left {stt_left}); "
          f"done already: {len(done)}", flush=True)
    for u, c in jobs:
        print(f"  - {pb.clip_id(u['id'], c)}  expect {u['expected']}", flush=True)

    if args.dry_run:
        for u in utts:
            p = clean_entry(u)
            if p:
                meta = make_variants(u, p, seed=args.seed + pb.CORPUS.index(u))
                print(f"  {u['id']}: variants ready {sorted(meta)}", flush=True)
            else:
                print(f"  {u['id']}: clean clip not cached yet (needs 1 TTS)", flush=True)
        print("dry run: no Gnani calls made", flush=True)
        return 0

    if len(need_tts) > tts_left:
        raise SystemExit(f"needs {len(need_tts)} TTS but only {tts_left} left in the budget")
    if not config.gnani_key():
        raise SystemExit("GNANI_API_KEY is not set")

    gnani._default = gnani.GnaniClient(max_attempts=1, backoff_s=0.0)
    run_log = {"at": now(), "conditions": conds, "tts": 0, "stt": 0, "stopped": None}
    res["calls"]["runs"].append(run_log)
    take_lock(args.lock_wait)
    code = 0
    try:
        for u in need_tts:
            try:
                await tts_cache.synth(u["text"], u["tts_lang"], voice=u["voice"])
            except gnani.GnaniError as e:
                run_log["stopped"] = f"TTS {u['id']}: {e.status} {e.code}"
                print("STOP:", run_log["stopped"], flush=True)
                return 2  # any TTS failure stops the run (no clean clip, nothing to test)
            finally:
                n = tts_cache.SYNTH_CALLS["count"]
                res["calls"]["tts"] += n - run_log["tts"]
                run_log["tts"] = n
                save(res)
            print(f"TTS {u['id']} ({u['voice']}) ok; TTS calls this run {run_log['tts']}", flush=True)

        metas = {u["id"]: make_variants(u, clean_entry(u), seed=args.seed + pb.CORPUS.index(u)) for u in utts}

        for u, c in jobs:
            if res["calls"]["stt"] >= args.max_stt:
                run_log["stopped"] = f"STT budget {args.max_stt} reached"
                print("STOP:", run_log["stopped"], flush=True)
                break
            cid = pb.clip_id(u["id"], c)
            p = audio_path(cid)
            data = p.read_bytes()
            before = gnani.STATS.stt
            t0 = time.perf_counter()
            row = {"clip_id": cid, "utt_id": u["id"], "lang": u["lang"], "voice": u["voice"], "condition": c,
                   "snr_db": metas[u["id"]][c]["snr_db"], "text": u["text"], "gloss": u["gloss"],
                   "expected": u["expected"], "audio": p.name, "clean_audio": metas[u["id"]]["clean"]["file"],
                   "duration_s": metas[u["id"]][c]["duration_s"], "sample_rate": metas[u["id"]][c]["sample_rate"],
                   "stt_lang": STT_LANG[u["lang"]], "at": now()}
            try:
                r = await transcribe_upload(data, p.name, lang=STT_LANG[u["lang"]])
            except gnani.GnaniError as e:
                row.update(transcript=None, error=f"{e.status} {e.code}")
                res["clips"] = [x for x in res["clips"] if x["clip_id"] != cid] + [row]
                if e.status in STOP_STATUSES:
                    run_log["stopped"] = f"STT {cid}: HTTP {e.status} {e.code}"
                    print("STOP:", run_log["stopped"], flush=True)
                    code = 2
                    break
                print(f"STT {cid} failed: {e.status} {e.code}", flush=True)
                continue
            finally:
                spent = gnani.STATS.stt - before
                res["calls"]["stt"] += spent
                run_log["stt"] += spent
                save(res)
            row["latency_s"] = round(time.perf_counter() - t0, 3)
            row.update(transcript=r["transcript"], stt_language_code=r["language_code"], mode=r["mode"],
                       model=r["model"], detected_language=r.get("detected_language_code"), error=None)
            row.update(pb.score(u["expected"], r["transcript"], u["lang"], said=u["text"]))
            res["clips"] = [x for x in res["clips"] if x["clip_id"] != cid] + [row]
            save(res)
            mark = "EXACT" if row["match"] else "MISS "
            print(f"{mark} {cid}: expected {u['expected']} heard {row['heard']} ({row['latency_s']} s) "
                  f"| STT calls total {res['calls']['stt']}", flush=True)
    finally:
        release_lock()
        save(res)
    s = res["summary"]
    print("\nper condition:", flush=True)
    for pc in s["per_condition"]:
        print(f"  {pc['condition']:12s} {pc['exact']}/{pc['amounts']} amounts exact ({pc['rate']}%), "
              f"{pc['clips_exact']}/{pc['clips']} clips clean", flush=True)
    print("headline:", (s.get("headline") or {}).get("text"), flush=True)
    print(f"calls this run: TTS {run_log['tts']}, STT {run_log['stt']}; totals: TTS {res['calls']['tts']}, "
          f"STT {res['calls']['stt']}", flush=True)
    print(f"results: {RESULTS}", flush=True)
    return code


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="no Gnani calls: check the corpus, build cached variants")
    ap.add_argument("--limit", type=int, default=None, help="at most N new STT clips this run")
    ap.add_argument("--conditions", default="clean,combined", help=f"comma list of {pb.CONDITION_ORDER}")
    ap.add_argument("--utts", default="", help="comma list of corpus ids (default: all 12)")
    ap.add_argument("--max-tts", type=int, default=12, help="total TTS budget across runs")
    ap.add_argument("--max-stt", type=int, default=36, help="total STT budget across runs")
    ap.add_argument("--export-seed", action="store_true", help="copy results + scored audio to seed_cache/bench and exit")
    ap.add_argument("--rescore", action="store_true", help="re-score saved transcripts offline and exit")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--lock-wait", type=float, default=1800.0, help="seconds to wait for the Gnani lock")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
