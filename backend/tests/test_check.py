"""Fair Pay Check (V01): calculation, parsing, the mic cap, and that nothing is stored. Gnani is mocked."""
from __future__ import annotations

import datetime as dt

import httpx
import pytest
from fastapi.testclient import TestClient

from app import wages
from app.check_core import compute, current_month, parse_spoken
from app.main import app
from app.routes import check as check_route
from tests.conftest import multipart_fields


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_guard(monkeypatch):
    check_route.GUARD.reset()
    monkeypatch.delenv("CHECK_STT_PER_IP_DAY", raising=False)
    monkeypatch.delenv("CHECK_STT_GLOBAL_DAY", raising=False)
    yield
    check_route.GUARD.reset()


# --------------------------------------------------------------------------- compute: full-time
@pytest.mark.parametrize("work_type,category,monthly", [
    ("maid", "unskilled", 16000.0), ("cooking", "skilled", 18500.0),
    ("care", "unskilled", 16000.0), ("both", "unskilled", 16000.0)])
def test_full_time_uses_notified_rate(work_type, category, monthly):
    r = compute(work_type, 8, 6, 9000)
    assert r["category"] == category
    assert r["minimum_monthly"] == monthly == wages.GO6_MONTHLY[category]
    assert r["is_estimate"] is False
    assert r["gap_monthly"] == monthly - 9000
    assert r["verdict"] == "below"
    assert "G.O.Ms.No.6" in r["source"] and "Zone-I" in r["source"]


def test_full_time_maid_numbers():
    r = compute("maid", 8, 6, 9000)
    assert r["working_days_per_month"] == 26
    assert r["gap_monthly"] == 7000
    assert r["per_day_to_close"] == 270  # 7000 / 26 = 269.23 -> rounded up so it really closes the gap
    assert r["gap_yearly"] == 84000
    assert "Full-time" in r["how"] and "615.50" in r["how"]


def test_more_than_8_hours_is_capped_and_noted():
    r = compute("maid", 10, 6, 16000)
    assert r["minimum_monthly"] == 16000 and r["is_estimate"] is False
    assert r["verdict"] == "fair"
    assert any("overtime" in n for n in r["notes"])


# --------------------------------------------------------------------------- compute: part-time (estimate)
def test_part_time_maid_matches_brief_example():
    r = compute("maid", 2, 6, 2500)
    assert r["is_estimate"] is True
    assert r["minimum_monthly"] == 4000.0  # 16000 / 26 / 8 x 2 x 26
    assert r["gap_monthly"] == 1500.0
    assert r["per_day_to_close"] == 58  # "Rs 58 a day"
    assert r["how"].startswith("Estimate:")
    assert "does not list part-time rates" in r["how"]
    assert "estimate" in r["source"].lower()
    assert "estimated minimum" in r["explanation"]


def test_part_time_cook_matches_ideas_file():
    r = compute("cooking", 3, 6, 3000)
    assert r["minimum_monthly"] == 6937.5 and r["gap_monthly"] == 3937.5
    assert r["per_day_to_close"] == 152  # 3937.5 / 26 = 151.44 -> 152


def test_fewer_days_pro_rates_working_days():
    r = compute("maid", 1, 3, 500)
    assert r["working_days_per_month"] == 13
    assert r["minimum_monthly"] == 1000.0  # 16000/26/8 x 1 x 13
    assert r["per_day_to_close"] == math_ceil(500 / 13)


def math_ceil(x: float) -> int:
    import math
    return math.ceil(x)


def test_full_hours_but_five_days_is_an_estimate():
    r = compute("maid", 8, 5, 10000)
    assert r["is_estimate"] is True
    assert r["minimum_monthly"] == wages.round50(16000 / 26 / 8 * 8 * (26 * 5 / 6))


def test_seven_days_capped_at_26_and_noted():
    r = compute("maid", 8, 7, 16000)
    assert r["minimum_monthly"] == 16000 and r["is_estimate"] is False
    assert any("rest day" in n for n in r["notes"])


def test_both_shows_cook_rate_as_alternative():
    r = compute("both", 2, 6, 2500)
    assert r["minimum_monthly"] == 4000.0
    assert r["alt_rate"]["minimum_monthly"] == 4625.0
    assert r["alt_rate"]["gap_monthly"] == 2125.0
    assert any("Cook" in n for n in r["notes"])
    assert compute("maid", 2, 6, 2500)["alt_rate"] is None


# --------------------------------------------------------------------------- compute: at or above
@pytest.mark.parametrize("pay", [4000, 4000.004, 5000, 20000])
def test_at_or_above_minimum_is_fair(pay):
    r = compute("maid", 2, 6, pay)
    assert r["verdict"] == "fair"
    assert r["gap_monthly"] == 0 and r["per_day_to_close"] == 0 and r["gap_yearly"] == 0
    assert "paying fair" in r["explanation"] and "Thank you" in r["explanation"]


def test_one_rupee_below_is_below():
    r = compute("maid", 2, 6, 3999)
    assert r["verdict"] == "below" and r["gap_monthly"] == 1 and r["per_day_to_close"] == 1


def test_zero_pay():
    r = compute("cooking", 1, 6, 0)
    assert r["gap_monthly"] == r["minimum_monthly"] == 2312.5


def test_tone_is_information_not_accusation():
    r = compute("maid", 1, 6, 500)
    text = " ".join([r["explanation"], r["how"], *r["notes"], r["disclaimer"]]).lower()
    for bad in ("illegal", "breaking the law", "violation", "offence", "penalty", "jail", "police", "fine"):
        assert bad not in text.replace("defined", "")
    assert "not legal advice" in r["disclaimer"].lower()
    assert any("VDA" in n for n in r["notes"])
    assert any("GHMC" in n for n in r["notes"])


def test_month_never_before_go6():
    assert current_month(dt.date(2026, 3, 15)) == "2026-06"
    assert current_month(dt.date(2026, 11, 9)) == "2026-11"


def test_unknown_work_type_raises():
    with pytest.raises(ValueError):
        compute("driver", 8, 6, 1000)


# --------------------------------------------------------------------------- the API
def test_api_check(client):
    r = client.post("/api/check", json={"work_type": "maid", "hours_per_day": 2, "days_per_week": 6,
                                        "monthly_pay": 2500})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    b = r.json()
    for k in ("minimum_monthly", "is_estimate", "category", "gap_monthly", "per_day_to_close", "verdict",
              "source", "explanation"):
        assert k in b
    assert b["per_day_to_close"] == 58 and b["verdict"] == "below"


@pytest.mark.parametrize("bad", [
    {"work_type": "driver", "hours_per_day": 2, "days_per_week": 6, "monthly_pay": 1},
    {"work_type": "maid", "hours_per_day": 0, "days_per_week": 6, "monthly_pay": 1},
    {"work_type": "maid", "hours_per_day": 17, "days_per_week": 6, "monthly_pay": 1},
    {"work_type": "maid", "hours_per_day": 2, "days_per_week": 0, "monthly_pay": 1},
    {"work_type": "maid", "hours_per_day": 2, "days_per_week": 8, "monthly_pay": 1},
    {"work_type": "maid", "hours_per_day": 2, "days_per_week": 6, "monthly_pay": -5},
    {"work_type": "maid", "hours_per_day": 2, "days_per_week": 6},
])
def test_api_check_validation(client, bad):
    assert client.post("/api/check", json=bad).status_code == 422


def test_api_stores_nothing(client):
    from sqlmodel import Session, select

    from app import db, models
    import sqlmodel

    def counts():
        with Session(db.get_engine()) as s:
            out = {}
            for table in sqlmodel.SQLModel.metadata.sorted_tables:
                out[table.name] = len(s.exec(select(table)).all())
            return out

    before = counts()
    client.post("/api/check", json={"work_type": "cooking", "hours_per_day": 3, "days_per_week": 6,
                                    "monthly_pay": 3000})
    client.post("/api/check/parse", json={"text": "do ghante, chhe din, teen hazaar"})
    assert counts() == before
    assert models  # imported so every table is registered


def test_options(client):
    b = client.get("/api/check/options").json()
    assert [w["id"] for w in b["work_types"]] == ["maid", "cooking", "both", "care"]


# --------------------------------------------------------------------------- parsing
@pytest.mark.parametrize("text,expected", [
    ("do ghante roz, chhe din, teen hazaar deta hoon", (None, 2, 6, 3000)),
    ("दो घंटे रोज़, छह दिन, तीन हज़ार देता हूँ", (None, 2, 6, 3000)),
    ("cooking 3 hours daily, 6 days a week, 3000 rupees", ("cooking", 3, 6, 3000)),
    ("safai aur khana, dhai ghante, saaton din, dhai hazaar mahina", ("both", 2.5, 7, 2500)),
    ("bachche ki dekhbhaal, aath ghante, sunday chhutti, barah hazaar", ("care", 8, 6, 12000)),
    ("jhaadu pocha bartan, derh ghanta, che din, do hazar paanch sau", ("maid", 1.5, 6, 2500)),
    ("खाना बनाती है, तीन घंटे, छह दिन, चार हज़ार", ("cooking", 3, 6, 4000)),
    ("maid aati hai ek ghanta, paanch din, 1500", ("maid", 1, 5, 1500)),
])
def test_parse_spoken(text, expected):
    p = parse_spoken(text)
    assert (p["work_type"], p["hours_per_day"], p["days_per_week"], p["monthly_pay"]) == expected


def test_parse_missing_fields_and_no_false_care():
    p = parse_spoken("wo aaya nahi")  # "aaya" = came, not an ayah
    assert p["work_type"] is None
    assert p["missing"] == ["work_type", "hours_per_day", "days_per_week", "monthly_pay"]
    assert parse_spoken("")["missing"] == ["work_type", "hours_per_day", "days_per_week", "monthly_pay"]


def test_api_parse_fills_work_type_and_computes(client):
    r = client.post("/api/check/parse", json={"text": "do ghante, chhe din, teen hazaar", "work_type": "maid"})
    b = r.json()
    assert b["parsed"]["missing"] == []
    assert b["result"]["minimum_monthly"] == 4000.0 and b["result"]["gap_monthly"] == 1000.0
    r = client.post("/api/check/parse", json={"text": "do ghante, teen hazaar"})
    assert r.json()["result"] is None and "days_per_week" in r.json()["parsed"]["missing"]


# --------------------------------------------------------------------------- speak (mocked Gnani)
def _stt_reply(text: str):
    def reply(request):
        f = multipart_fields(request)
        assert f["language_code"] == "hi-IN,en-IN"
        assert f["format"] == "codemix"
        return httpx.Response(200, json={"success": True, "transcript": text, "detected_language_code": "hi-IN"})
    return reply


def test_speak_parses_and_computes(client, mock_gnani, short_ogg):
    mock_gnani.push("/stt/v3", _stt_reply("खाना बनाती है, तीन घंटे, छह दिन, तीन हज़ार देता हूँ"))
    r = client.post("/api/check/speak", files={"audio": ("rec.ogg", short_ogg, "audio/ogg")})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["parsed"]["work_type"] == "cooking"
    assert b["result"]["minimum_monthly"] == 6937.5
    assert b["remaining_today"] == 2
    assert r.headers["cache-control"] == "no-store"


def test_speak_uses_tapped_work_type(client, mock_gnani, short_ogg):
    mock_gnani.push("/stt/v3", _stt_reply("do ghante roz, chhe din, teen hazaar"))
    r = client.post("/api/check/speak", files={"audio": ("rec.ogg", short_ogg, "audio/ogg")},
                    data={"work_type": "maid"})
    assert r.json()["result"]["gap_monthly"] == 1000.0


def test_speak_cap_per_ip(client, mock_gnani, short_ogg, monkeypatch):
    monkeypatch.setenv("CHECK_STT_PER_IP_DAY", "2")
    mock_gnani.default["/stt/v3"] = _stt_reply("do ghante")
    hdr = {"x-forwarded-for": "203.0.113.7"}
    for left in (1, 0):
        r = client.post("/api/check/speak", files={"audio": ("r.ogg", short_ogg, "audio/ogg")}, headers=hdr)
        assert r.status_code == 200 and r.json()["remaining_today"] == left
    r = client.post("/api/check/speak", files={"audio": ("r.ogg", short_ogg, "audio/ogg")}, headers=hdr)
    assert r.status_code == 429 and r.json()["fallback"] == "tap"
    assert len(mock_gnani.requests) == 2  # the capped request never reached Gnani
    # another visitor still has their own tries
    other = client.post("/api/check/speak", files={"audio": ("r.ogg", short_ogg, "audio/ogg")},
                        headers={"x-forwarded-for": "198.51.100.2"})
    assert other.status_code == 200
    q = client.get("/api/check/speak/quota", headers=hdr).json()
    assert q == {"remaining_today": 0, "per_day": 2}


def test_speak_global_cap(client, mock_gnani, short_ogg, monkeypatch):
    monkeypatch.setenv("CHECK_STT_GLOBAL_DAY", "1")
    mock_gnani.default["/stt/v3"] = _stt_reply("do ghante")
    assert client.post("/api/check/speak", files={"audio": ("r.ogg", short_ogg, "audio/ogg")},
                       headers={"x-forwarded-for": "a"}).status_code == 200
    assert client.post("/api/check/speak", files={"audio": ("r.ogg", short_ogg, "audio/ogg")},
                       headers={"x-forwarded-for": "b"}).status_code == 429


def test_speak_gnani_down_falls_back(client, mock_gnani, short_ogg):
    mock_gnani.default["/stt/v3"] = httpx.Response(500, json={"detail": {"error_code": "X", "message": "down"}})
    r = client.post("/api/check/speak", files={"audio": ("r.ogg", short_ogg, "audio/ogg")})
    assert r.status_code == 503 and r.json()["fallback"] == "tap"


def test_speak_without_key_falls_back(client, short_ogg):
    r = client.post("/api/check/speak", files={"audio": ("r.ogg", short_ogg, "audio/ogg")})
    assert r.status_code == 503 and r.json()["fallback"] == "tap"


def test_speak_rejects_long_and_bad_audio(client, mock_gnani, long_wav):
    r = client.post("/api/check/speak", files={"audio": ("r.wav", long_wav, "audio/wav")})
    assert r.status_code == 413 and r.json()["error"] == "too_long"
    assert client.post("/api/check/speak", files={"audio": ("x.txt", b"hi", "text/plain")}).status_code == 415
    assert client.post("/api/check/speak", files={"audio": ("x.ogg", b"", "audio/ogg")}).status_code == 400
    assert mock_gnani.requests == []
    assert check_route.GUARD.remaining("testclient") == 3  # rejected uploads don't use a try


def test_client_ip_header_order(client):
    q = lambda h: client.get("/api/check/speak/quota", headers=h).json()["remaining_today"]
    check_route.GUARD.take("198.51.100.50")
    assert q({"cf-connecting-ip": "198.51.100.50", "x-forwarded-for": "10.0.0.1"}) == 2
    assert q({"x-forwarded-for": "198.51.100.50, 10.0.0.1"}) == 2
    assert q({"x-real-ip": "198.51.100.50"}) == 2
    assert q({"x-forwarded-for": "192.0.2.1"}) == 3
