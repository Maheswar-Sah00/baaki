# Baaki · బాకీ

Baaki ("money still owed") is a voice-first web app (mobile PWA) for domestic workers in Hyderabad who are unpaid or underpaid.
She says what she is owed in Telugu or Hinglish; Baaki adds it up against the law, reads it back, and sends the employer a polite voice note in the employer's language.

Built for the Gnani.ai Great Indian AI Internship Challenge. Prototype: synthetic data only, not legal advice.

## Run the demo (one command, local only)

Needs Python 3.12 and Node 22, keys in `.env` at the project root (copy `.env.example`), and a one-time install:

```powershell
cd backend; python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt; cd ..
cd web; npm ci; cd ..
```

Then:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-demo.ps1   # backend :8020, production web :3020, fresh demo story
powershell -ExecutionPolicy Bypass -File scripts\stop-demo.ps1    # stops only what start-demo started
```

`start-demo.ps1` starts the backend on `127.0.0.1:8020`, builds the web app with `BACKEND_URL=http://127.0.0.1:8020`
(skipped when the build is newer than the sources; `-NoBuild` skips it, `-Rebuild` forces it), runs `next start -p 3020`,
calls `POST /api/demo/reset` and prints the URLs, including the seeded employer link. Logs and PIDs go to `B:\tmp`
(`baaki-demo-*.log`, `baaki-demo-pids.json`). Options: `-NoInterim` (the meter updates only after she stops: fewer STT
calls), `-SiteUrl https://...` (the public origin used in link previews and in the links Baaki writes).

Filming morning, with the demo running:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\warm-demo.ps1    # re-warms the voice clips, then resets the story
```

The Polite note says a reply-by date (today + 7 days), so that one sentence is new each day (1 Timbre call). The other demo
clips (the rest of the Polite note, the filming-story read-back, "Paisa aa gaya") are pre-rendered in `backend/seed_cache`
(`demo_manifest.json`), so a cold start spends nothing on them. `-Export` copies newly warmed clips into the seed cache.

**Microphone and HTTPS.** Browsers only allow the mic on `https://` or `localhost`. For filming, either record in desktop
Chrome on `http://localhost:3020` with DevTools device mode (phone frame; the mic works on localhost), or put the app behind
a public HTTPS URL that you set up yourself and pass it as `-SiteUrl`. The scripts never expose anything to the internet.

## Routes

| Route | What it is |
|---|---|
| `/` | Website: the problem, how it works, the Gnani tech |
| `/app` | Worker app home: her homes and what each owes |
| `/speak` → `/case/new` | Speak (the Baaki Meter counts up while she talks) → read-back → "Haan, sahi hai" |
| `/case/{id}` | Case: Polite / Firm / Formal steps with voice notes, the Listen-twice badge, "Paisa aa gaya!" |
| `/e/{token}` | Employer page: plays the voice note, itemised dues, UPI, "I've paid", pay in parts, reply by voice. Link previews show no amount or name |
| `/inbox/{caseId}` | WhatsApp replies: add the employer's voice note or text; promises are tracked |
| `/exit?case={id}` | Exit Kit: asked to leave, final-dues due date, part-month pay, spoken checklist |
| `/check` | Fair Pay Check: employer self-check against Telangana's minimum wage (stores nothing) |
| `/proof` | Noise proof: 34 of 34 rupee amounts exact in 24 noisy clips, every clip playable, misses shown |
| `/diary`, `/voice`, `/safety`, `/r` | Work diary, opt-in voice clone, help lines, quick-exit page |

## Gnani features used

- **Prisma v3.0 STT** (`/stt/v3`): her speech in one request listing `te-IN,hi-IN,en-IN` (no language picker), `codemix`
  so spoken amounts survive, clips split at pauses under 28 s. Interim chunks every 4.5 s make the meter move while she
  talks. Also the employer's WhatsApp replies, the Fair Pay Check mic, and **Listen-twice**: Prisma re-hears every voice note
  before she sends it and checks each amount and the AI disclosure (it warns, it never blocks).
- **Timbre v3.0 TTS**: the read-back (`<slow>`, `<pauses>`), employer voice notes in Hinglish or Telugu with an AI
  disclosure first, and "Paisa aa gaya!" (`<excited>`). Disk cache per sentence, so a text is never synthesised twice.
- **Voice Clone** (`vachana-vc-v1`): opt-in, with consent, so the note can be in her own voice.
- One active request per account is respected (a global lock with backoff). Every rupee figure comes from our own
  Telugu/Hindi number parsers and the wage calculator, never from a language model.

## Development

```powershell
cd backend; .venv\Scripts\python -m uvicorn app.main:app --port 8020 --reload   # API
cd web; $env:BACKEND_URL="http://127.0.0.1:8020"; npm run dev                  # http://localhost:3000
cd backend; .venv\Scripts\python -m pytest                                       # 1,389 tests, offline (keys blanked)
cd web; npm run build
```

`GET /health` reports whether the keys are set and the Gnani calls made since start. Gnani API notes: `docs/gnani_api/`.
Design system: `docs/DESIGN_SYSTEM.md`. Link-preview image: `node web/scripts/make-og.mjs`.
