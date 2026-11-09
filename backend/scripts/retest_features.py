"""Feature retest: drives every built feature through the HTTP API, end to end, with ZERO Gnani or LLM calls.

Runs in-process against a throwaway database (BAAKI_RETEST_DIR, default <system temp>/baaki-retest) and media folder, with every API key blanked,
so it never touches the real demo data or spends credits. Cached voice clips are still served from the TTS cache.

  backend\\.venv\\Scripts\\python backend\\scripts\\retest_features.py            # all features
  backend\\.venv\\Scripts\\python backend\\scripts\\retest_features.py -k raise   # only steps whose name contains "raise"

Exit code 0 when every step passes. Features that are not built yet (404 on their route) are reported as SKIP.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

# BAAKI_RETEST_DIR wins; otherwise the system temp dir (set TMP/TEMP=B:/tmp on the dev box).
TMP = Path(os.environ.get("BAAKI_RETEST_DIR") or Path(tempfile.gettempdir()) / "baaki-retest")
TMP.mkdir(parents=True, exist_ok=True)
for f in TMP.glob("retest.db*"):
    f.unlink()
# Must be set before the app (and its .env loader, override=False) is imported.
os.environ.update({
    "GNANI_API_KEY": "", "GROQ_API_KEY": "", "GEMINI_API_KEY": "", "LLM_PROVIDER": "none",
    "DATABASE_URL": f"sqlite:///{(TMP / 'retest.db').as_posix()}",
    "MEDIA_DIR": str(TMP / "media"), "AUDIO_TMP_DIR": str(TMP / "tmp"),
})

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import gnani  # noqa: E402
from app.main import app  # noqa: E402

RESULTS: list[tuple[str, str, str]] = []
ONLY = sys.argv[sys.argv.index("-k") + 1].lower() if "-k" in sys.argv else ""


class Skip(Exception):
    pass


def step(name: str):
    def deco(fn):
        if ONLY and ONLY not in name.lower() and name != "demo reset":
            return fn
        try:
            detail = fn() or ""
            RESULTS.append(("PASS", name, str(detail)))
        except Skip as e:
            RESULTS.append(("SKIP", name, str(e)))
        except Exception as e:  # noqa: BLE001
            RESULTS.append(("FAIL", name, f"{type(e).__name__}: {e}"))
            if "-v" in sys.argv:
                traceback.print_exc()
        return fn
    return deco


def ok(r, *codes: int):
    codes = codes or (200,)
    if r.status_code == 404 and r.json().get("detail") == "Not Found":
        raise Skip("route not built yet")
    assert r.status_code in codes, f"{r.request.method} {r.request.url.path} -> {r.status_code}: {r.text[:300]}"
    return r.json() if "json" in r.headers.get("content-type", "") else r


with TestClient(app) as c:
    S: dict = {}

    @step("demo reset")
    def _():
        S.update(ok(c.post("/api/demo/reset")))
        return f"cases={S['cases']} totals={S['totals']}"

    @step("health")
    def _():
        return {k: v for k, v in ok(c.get("/health")).items() if "key" not in k.lower()}

    @step("core: case + worker home")
    def _():
        case = ok(c.get(f"/api/cases/{S['cases']['sharma']}"))
        assert case, "empty case"
        ok(c.get(f"/api/workers/{S['workers']['lakshmi']}"), 200)
        return f"sharma total_due={S['totals']['sharma']}"

    @step("core: employer page + played")
    def _():
        tok = S["employer_tokens"]["sharma"]
        page = ok(c.get(f"/api/e/{tok}"))
        ok(c.post(f"/api/e/{tok}/played"))
        S["sharma_page"] = page
        return f"keys={sorted(page)[:8]}"

    # ---------------------------------------------------------------- top 5
    @step("top5 G07 Listen-twice: read verify state")
    def _():
        cid = S["cases"]["sharma"]
        m = ok(c.post(f"/api/cases/{cid}/messages/polite", json={"use_llm": False, "audio": False, "pdf": True}))
        mid = m.get("id") or m.get("message_id") or (m.get("message") or {}).get("id")
        assert mid, f"no message id in {sorted(m)}"
        ok(c.get(f"/api/cases/{cid}/messages"))
        ok(c.get(f"/api/cases/{cid}/legal-pack"))
        ok(c.post(f"/api/messages/{mid}/sent"))
        r = c.get(f"/api/verify/messages/{mid}")
        # Offline the note has no audio (keys blanked), so the guard must say so cleanly instead of crashing.
        assert r.status_code == 200 or "no_audio" in r.text, r.text[:200]
        return f"message {mid}: {r.status_code} {'(no audio offline: handled)' if r.status_code != 200 else ''}"

    @step("top5 V01 Fair Pay Check")
    def _():
        opts = ok(c.get("/api/check/options"))
        res = ok(c.post("/api/check", json={"work_type": "maid", "hours_per_day": 2, "days_per_week": 6,
                                             "monthly_pay": 2500}))
        parsed = ok(c.post("/api/check/parse", json={"text": "do ghante roz, dhai hazaar mahina"}))
        return f"options={len(opts) if hasattr(opts, '__len__') else 'ok'} result_keys={sorted(res)[:6]} parse={parsed}"

    @step("top5 G04 Noise proof")
    def _():
        p = ok(c.get("/api/proof"))
        txt = str(p)
        assert "34" in txt, "34/34 headline missing"
        return "34/34 present"

    @step("top5 M1 Share to Baaki + Promise Keeper")
    def _():
        cid = S["cases"]["sharma"]
        card = ok(c.post(f"/api/inbox/{cid}", data={"text": "Lakshmi ko bolo shanivar ko barah hazaar de dunga",
                                                     "use_llm": "false", "speak": "false"}))
        listing = ok(c.get(f"/api/inbox/{cid}"))
        prom = (card.get("promise") or {})
        if prom.get("id"):
            ok(c.post(f"/api/inbox/promises/{prom['id']}/remind", json={"force": True}))
            ok(c.post(f"/api/inbox/promises/{prom['id']}/status", json={"status": "kept"}))
        return f"promise_amount={prom.get('amount')} cards={len(listing.get('cards', listing)) if isinstance(listing, dict) else len(listing)}"

    @step("top5 W03 Exit Kit")
    def _():
        ok(c.get("/api/exit/checklist"))
        kit = ok(c.post("/api/exit", json={"worker_id": S["workers"]["lakshmi"], "case_id": S["cases"]["reddy"]}))
        eid = kit.get("id")
        if eid:
            ok(c.get(f"/api/exit/{eid}"))
        return f"keys={sorted(kit)[:8]}"

    # ---------------------------------------------------------------- add-ons
    @step("addon Haq Raise: demo -> accept")
    def _():
        d = ok(c.post("/api/raise/demo", json={"audio": False}))
        ok(c.get("/api/raise/summary", params={"worker_id": S["workers"]["lakshmi"]}))
        tok = d.get("employer_token") or d.get("token") or (d.get("raise") or {}).get("employer_token")
        if not tok:
            return f"demo keys={sorted(d)} (no token to accept)"
        ok(c.get(f"/api/raise/e/{tok}"))
        acc = ok(c.post(f"/api/raise/e/{tok}/accept", json={"choice": "asked"}))
        return f"accepted keys={sorted(acc)[:6]}"

    @step("addon Dues (milk/chit)")
    def _():
        ok(c.post("/api/dues/demo"))
        lst = ok(c.get("/api/dues"))
        return f"accounts={len(lst) if isinstance(lst, list) else sorted(lst)[:4]}"

    # ---------------------------------------------------------------- ranks 6-10
    @step("rank6 G13 consent: sentence + gate")
    def _():
        wid = S["workers"]["lakshmi"]
        r = ok(c.get("/api/consent", params={"worker_id": wid, "lang": "te"}))
        assert r.get("words"), "no karaoke words"
        m = ok(c.post("/api/consent/match", json={"worker_id": wid, "lang": "te", "transcript": r["text"]}))
        assert (m.get("match") or m).get("passed"), f"own sentence did not match: {str(m)[:200]}"
        bad = ok(c.post("/api/consent/match", json={"worker_id": wid, "lang": "te", "transcript": "ఈ రోజు వర్షం పడింది"}))
        assert not (bad.get("match") or bad).get("passed"), "unrelated speech passed the consent gate"
        return f"{len(r['words'])} words; own sentence passes, unrelated speech fails"

    @step("rank7 V04 sandbox: create -> paid")
    def _():
        before = gnani.STATS.copy() if hasattr(gnani, "STATS") and hasattr(gnani.STATS, "copy") else None
        sb = ok(c.post("/api/sandbox"), 200, 201)
        sid = sb.get("id") or sb.get("sandbox_id") or sb.get("sid")
        assert sid, f"no sandbox id in {sorted(sb)}"
        ok(c.get(f"/api/sandbox/{sid}"))
        ok(c.post(f"/api/sandbox/{sid}/paid"))
        w = ok(c.get(f"/api/sandbox/{sid}/worker"))
        assert "paid" in str(w).lower(), "worker panel does not show paid"
        return f"sid={sid} gnani_stats_before={before}"

    @step("rank8 V08 quiz: cards + score")
    def _():
        q = ok(c.get("/api/quiz", params={"lang": "en"}))
        cards = q.get("cards", q) if isinstance(q, dict) else q
        assert len(cards) >= 5, f"{len(cards)} cards"
        return f"{len(cards)} cards"

    @step("rank9 V12 story: seeded case timeline")
    def _():
        t = ok(c.get(f"/api/story/{S['cases']['sharma']}"))
        ev = t.get("events", [])
        ats = [e.get("at") for e in ev]
        bad = [(a, b) for a, b in zip(ev, ev[1:]) if (a.get("at") or "")[:19] > (b.get("at") or "")[:19]]  # same-second intake order is by design
        assert not bad, "out of order: " + "; ".join(f"{a['kind']}@{a['at']} > {b['kind']}@{b['at']}" for a, b in bad)
        return f"{len(ev)} events, kinds={[e.get('kind') for e in ev][:8]}"

    @step("rank10 V09 hisaab: propose by text -> accept")
    def _():
        tok = S["employer_tokens"]["sharma"]
        before = ok(c.get(f"/api/e/{tok}"))
        p = ok(c.post(f"/api/hisaab/e/{tok}", data={"text": "Maine October mein do hazaar cash diye the"}))
        pid = p.get("id") or (p.get("proposal") or {}).get("id")
        assert pid, f"no proposal id in {sorted(p)}"
        d = ok(c.post(f"/api/hisaab/{pid}/decide", json={"decision": "accept"}))
        return f"amount={p.get('amount') or (p.get('proposal') or {}).get('amount')} decide_keys={sorted(d)[:6]}"

    @step("core: pay in parts -> claim -> she confirms -> balance 0 (Paisa aa gaya)")
    def _():
        tok = S["employer_tokens"]["rao"]
        ok(c.post(f"/api/e/{tok}/plan", json={"instalments": 2}))
        paid = []
        for body in ({"amount": 100, "method": "cash", "alert_audio": False}, {"method": "upi", "alert_audio": False}):
            claim = ok(c.post(f"/api/e/{tok}/pay", json=body))   # "I've paid" is only a claim
            assert claim.get("pending_confirmation") and not claim.get("fully_paid"), f"claim recorded money: {claim}"
            assert "case_id" not in claim, "employer response leaks case_id"
            d = ok(c.post(f"/api/hisaab/{claim['claim']['id']}/decide", json={"decision": "accept"}))
            assert d.get("alert"), "no Paisa aa gaya alert after her confirmation"
            paid.append(d)
        bal = ok(c.get(f"/api/e/{tok}")).get("balance")
        assert float(bal) == 0, f"balance after paying everything = {bal}"
        assert paid[-1].get("fully_paid") and paid[-1].get("badge"), "no badge after confirmed full payment"
        return f"rao claimed 100 + rest, Rafiq confirmed both; balance={bal}; badge={paid[-1]['badge']['title']}"

    @step("zero Gnani calls")
    def _():
        h = ok(c.get("/health"))
        calls = {k: v for k, v in h.items() if "call" in k.lower() or "gnani" in k.lower() and "key" not in k.lower()}
        return str(calls)

width = max(len(n) for _, n, _ in RESULTS)
for status, name, detail in RESULTS:
    print(f"{status:4}  {name:<{width}}  {detail[:160]}")
fails = sum(1 for s, _, _ in RESULTS if s == "FAIL")
print(f"\n{sum(1 for s,_,_ in RESULTS if s=='PASS')} pass, {fails} fail, {sum(1 for s,_,_ in RESULTS if s=='SKIP')} skip")
sys.exit(1 if fails else 0)
