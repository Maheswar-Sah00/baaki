# Baaki

Voice-first web app (mobile PWA) for domestic workers in Hyderabad who are unpaid or underpaid.
The worker speaks Telugu or Hinglish; Baaki transcribes it (Gnani Prisma), works out the money still
owed (*baaki*), and drafts a letter and a voice note for the employer in the employer's language
(Gnani Timbre). Works both ways: Telugu worker with a Hinglish employer, or the reverse.

**Status: skeleton.** Voice plumbing works (STT, TTS, PDF shaping, LLM client). Cases, calculator
and letters are placeholders that return 501.

## Run

Requires Python 3.12 and Node 22. Put your keys in `.env` at the project root (see `.env.example`).

Backend (FastAPI, port 8000):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000 --reload
```

Web (Next.js, port 3000; proxies `/api/*` to the backend):

```powershell
cd web
npm ci
npm run dev        # http://localhost:3000
npm run build      # production build
```

Tests and smoke test:

```powershell
cd backend
.venv\Scripts\python -m pytest                       # offline, no keys used
.venv\Scripts\python scripts\smoke_roundtrip.py      # real Gnani key: TTS -> STT (Telugu + Hinglish)
```

## API (so far)

| Route | What it does |
|---|---|
| `GET /health`, `GET /api/health` | Liveness, and whether Gnani / LLM keys are set |
| `POST /api/stt` | Multipart `audio` (+ `lang` = `te` \| `hinglish` \| `auto`, `mode` = `transcribe`...) → transcript |
| `POST /api/tts` | JSON `{text, lang: te-IN \| hi-IN \| hi-en, voice?, model?}` → OGG/MP3 audio (cached) |
| `GET /api/voices` | Timbre voices and defaults |
| `/api/cases/...`, `/api/cases/{id}/letters/...` | Placeholders (501) |

Gnani API docs (copied from docs.gnani.ai): `docs/gnani_api/`.

Prototype. Synthetic data only. Not legal advice.
