# 04. Gnani feasibility: voice clone, audio tags, dropped number

Run 9 Nov 2026 with the real key, all calls one after another. Synthetic data only: the "worker"
reference voice is itself a Timbre voice (Kalpana), and Lakshmi and Sharma ji are fictional.
Script: `backend/scripts/feasibility_gnani.py` (steps `t3a`, `t1`, `t2`, `t3b`; finished steps are
skipped on a re-run). Raw results: `backend/data/feasibility/results.json`. Audio is in
`backend/data/feasibility/` (gitignored). **Listen to the files before deciding**: everything below
is judged from transcripts, durations, silences and loudness only.

**Calls spent: 21** (STT 9, Timbre TTS 7, VC embedding 1, VC TTS 4). No credit or balance header is
returned on any response, so check the remaining balance at app.gnani.ai.

## Verdicts

| Test | Verdict |
|---|---|
| 1. Cross-lingual voice clone (Telugu reference, Hinglish output) | **Works.** Every word and the amount survive; latency 3.5 to 8.3 s. Speech is fast and has no pauses (see notes). |
| 2. Audio tags on timbre-v3.0 | **`<pauses>` works in Hinglish (hi-en) and Telugu (te-IN).** Tags are never spoken. `<slow>` and `<excited>` cannot be confirmed without listening. |
| 3. Dropped "बारह" | **STT problem, not TTS.** `format=transcribe` with `language_code=hi-IN,en-IN` dropped it. TTS says "बारह हज़ार" every time. |

## Working request formats

Base `https://api.vachana.ai`. Header `X-API-Key-ID` on every call (plus `Content-Type: application/json` for JSON).

**VC embedding**: `POST /api/v1/tts/voice-clone/embeddings`, multipart, one field `audio_file`
(we sent `t1_reference....wav`, `audio/wav`, 24 kHz mono 16-bit, 19.3 s; the docs say 5 to 30 s).
Response `data.voice_clone_embedding` = `{embedding: <4,096-char string>, shape: [1, 768], dtype: "torch.bfloat16"}`. 1.17 s.
Generate it once per worker and cache it (`t1_speaker_embedding.json`, gitignored).

**VC TTS**: `POST /api/v1/tts/inference`, JSON:
```json
{"text": "...", "model": "vachana-vc-v1",
 "speaker_embedding": {"embedding": "...", "shape": [1, 768], "dtype": "torch.bfloat16"},
 "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2, "container": "wav", "encoding": "linear_pcm"}}
```
No `voice` or `language` field. The response is the WAV bytes. (OGG output from VC was not tested; convert the WAV with `audio.whatsappify()`.)

**Timbre TTS with tags**: same endpoint, JSON `{text, voice, model: "timbre-v3.0", language: "hi-en" | "te-IN", audio_config: {sample_rate: 48000, num_channels: 1, sample_width: 2, container: "ogg", encoding: "oggopus"}}`.

**Prisma STT**: `POST /stt/v3`, multipart `audio_file` (file-name extension sets the format) plus
`language_code`, `format`, `model=prisma-v3.0`.

Code: `gnani.voice_clone_embedding()` / `vc_embedding()` and `gnani.vc_tts()` in `backend/app/gnani.py`
(`vc_tts` now defaults to the verified WAV at 24 kHz, validates text and embedding, and sends only the three
embedding fields). Offline tests: `backend/tests/test_gnani_vc.py` (6 tests). Full suite: 1098 passed.

## Test 1: cross-lingual voice clone

Reference: `t1_reference_lakshmi_telugu_kalpana_v3.wav`, Timbre v3.0 Kalpana, te-IN, 3 sentences of
natural Telugu ("నమస్తే, నా పేరు లక్ష్మి..."), 19.28 s, TTS 4.09 s.

| Output file | Text | VC latency | Audio | Prisma transcript (hi-IN,en-IN, codemix) |
|---|---|---|---|---|
| `t1_vc_hinglish_roman.wav` | "Yeh sandesh Lakshmi ki anumati se ... total baarah hazaar rupaye ..." (Latin script) | 7.14 s | 11.19 s | ये संदेश लक्ष्मी की अनुमति से, उनकी आवाज़ में, बाकी अपने बनाया है, madam। नमस्ते मेरी तीन महीने की salary total **बारह हज़ार रुपये** अभी तक बाकी है क्या आप इस half दे सकती हैं। धन्यवाद। |
| `t1_vc_hinglish_devanagari.wav` | Same message in Devanagari (with "Baaki app", "salary", "total" in Latin) | 8.28 s | 11.02 s | यह संदेश लक्ष्मी की अनुमति से उनकी आवाज़ में बाकी आपने बनाया है, madam। नमस्ते मेरी तीन महीने की salary total **बारह हज़ार रुपये** अभी तक बाकी है क्या आप इस हफ्ते दे सकती हैं धन्यवाद। |
| `t1_vc_telugu.wav` | అమ్మగారు, నా మూడు నెలల జీతం, మొత్తం పన్నెండు వేల రూపాయలు, ఇంకా బాకీ ఉంది. | 3.47 s | 3.91 s | not transcribed (credit budget) |
| `t1_vc_english.wav` | Madam, my salary for three months, twelve thousand rupees in total, is still pending. | 3.71 s | 4.52 s | not transcribed |

Findings:
- **The cloned voice says the amount.** "baarah hazaar rupaye" came back as बारह हज़ार रुपये from both scripts.
- **Devanagari input is slightly cleaner**: "is hafte" was heard as "इस हफ्ते" (the Latin version gave "इस half").
- **The brand name blurs**: "Baaki app" was heard as "बाकी अपने / आपने" in both. In the disclosure, write "Baaki ऐप" or "बाकी ऐप" (or "Baaki application") and listen to the result.
- **Pace**: the VC output has no silence of 0.25 s or more (at -35 dB) anywhere, even at commas and full stops. The reference had 8 such pauses in 19 s. About 3.6 words/s, compared with about 2.6 for Shivani. It may sound rushed. For the employer voice note, send one sentence per call and join them with `audio.concat_with_gaps()` (about 0.4 s).
- **Does it sound like her?** We cannot tell from numbers. Loudness matches the reference (mean -16 dB vs -15 dB). Compare `t1_reference_...wav` with the four `t1_vc_*.wav` files by ear.
- One embedding speaks Hinglish, Hindi, Telugu and English. No language field is needed.

## Test 2: audio tags (timbre-v3.0)

| File | Voice / lang | TTS latency | Audio | Silences ≥0.25 s [start, length] | Transcript |
|---|---|---|---|---|---|
| `t2_tags_hinglish_slow_readback_shivani_v3.ogg` | Shivani, hi-en | 2.66 s | 7.93 s | [1.31, **0.94**], [3.81, **0.68**], [4.84, 0.33], [6.24, **0.97**] | तीन महीने चार हज़ार हर महीना कुल बारह हज़ार रुपये सही है। (hi-IN,en-IN, codemix) |
| `t2_tags_hinglish_excited_shivani_v3.ogg` | Shivani, hi-en | 1.56 s | 3.61 s | none | not transcribed |
| `t2_tags_telugu_slow_readback_kalpana_v3.ogg` | Kalpana, te-IN | 2.26 s | 7.21 s | [1.16, **0.82**], [3.56, **0.72**], [5.70, **0.79**] | మూడు నెలలు, నెలకు నాలుగు వేలు, మొత్తం పన్నెండు వేలు సరేనా. (te-IN,en-IN, verbatim) |
| `t2_tags_telugu_excited_kalpana_v3.ogg` | Kalpana, te-IN | 1.29 s | 1.53 s | [1.17, 0.35] | not transcribed |

Texts sent: exactly the brief's lines (`<slow> Teen mahine <pauses> chaar hazaar har mahina <pauses> kul baarah hazaar rupaye. <pauses> Sahi hai?`, `<excited> Paisa aa gaya! Sharma ji ne baarah hazaar rupaye bhej diye.`, and the Telugu `<slow> మూడు నెలలు, <pauses> నెలకు నాలుగు వేలు, <pauses> మొత్తం పన్నెండు వేలు. <pauses> సరేనా?`, `<excited> డబ్బులు వచ్చేశాయి!`).

- **`<pauses>` works in both languages**: each tag gives a gap of 0.7 to 1.0 s, against 0.3 to 0.5 s for a normal comma or full stop. Each file has exactly three long gaps, one per tag.
- **Tags are never spoken**: the transcripts contain no tag text, and every number survives.
- **`<slow>`**: speech without the silences runs about 2.6 words/s (Hinglish) and about 11 chars/s (Telugu, against about 12.5 in the smoke clip). That is at most slightly slower; listen to judge it.
- **`<excited>`**: the Telugu clip peaks at 0.0 dBFS (louder than the other Kalpana clips at -4 dB). The Hinglish clip shows no clear change. Listen to judge both.
- **Loudness**: Shivani v3 (hi-en) clips are about 7 dB quieter (mean -22 to -24 dB) than Kalpana, Poorvi or VC (-15 to -17 dB). Normalise loudness (ffmpeg `loudnorm`) before playing or sending them.
- For the read-back, `<pauses>` between facts is the reliable tool. A Telugu or Hinglish read-back runs 7 to 8 s for three facts.

## Test 3: the dropped number

Original smoke result: Shivani v3.0 hi-en said "... Total बारह हज़ार रुपये बाकी हैं." With
`hi-IN,en-IN` and `transcribe`, the transcript was "total हज़ार रुपये बाकी हैं।"

**(a) The same smoke audio (`backend/data/smoke/hinglish_tts.ogg`) re-transcribed:**

| language_code | format | Latency | Transcript |
|---|---|---|---|
| hi-IN,en-IN | transcribe (smoke run) | 1.77 s | ... total **हज़ार रुपये** बाकी हैं। ✗ |
| hi-IN,en-IN | verbatim | 1.49 s | मैडम, मेरी तीन महीने की सैलरी अभी तक नहीं मिली, टोटल **बारह हज़ार रुपये** बाकी हैं। ✓ (English words in Devanagari) |
| hi-IN,en-IN | codemix | 0.93 s | मैडम, मेरी तीन महीने की salary अभी तक नहीं मिली, total **बारह हज़ार रुपये** बाकी हैं। ✓ |
| hi-IN | transcribe | 0.87 s | Madam, मेरी 3 महीने की salary अभी तक नहीं मिली, total **12,000** रुपये बाकी हैं। ✓ |

Prisma hears "बारह" in every run. The number is lost in the inverse text normalisation (ITN) step,
which turns number words into digits. `transcribe` runs ITN, and it drops the number only when the
request lists more than one language (`hi-IN,en-IN`). The audio was fine.

**(b, c) TTS amount formats, transcribed with hi-IN,en-IN + codemix:**

| File | Model / voice | Amount written as | TTS latency | Audio | Transcript |
|---|---|---|---|---|---|
| `t3b_poorvi_v25_words_devanagari.ogg` | timbre-v2.5 Poorvi, hi-en | बारह हज़ार रुपये | 1.19 s | 4.81 s | ... total **बारह हज़ार रुपये** बाकी हैं। ✓ |
| `t3b_shivani_v3_digits.ogg` | timbre-v3.0 Shivani, hi-en | ₹12,000 | 2.37 s | 5.37 s | ... total **बारह हज़ार रुपये** बाकी हैं। ✓ (TN read ₹12,000 as "बारह हज़ार रुपये") |
| smoke `hinglish_tts.ogg` | timbre-v3.0 Shivani, hi-en | बारह हज़ार रुपये | 2.88 s | 6.09 s | ✓ (row (a) codemix) |
| `t1_vc_hinglish_roman.wav` | vachana-vc-v1 | baarah hazaar rupaye | 7.14 s | 11.19 s | ✓ (Test 1) |

Poorvi v2.5 is the fastest (1.2 s) and is not quiet. Shivani v3 is needed for tags.

**Recommendations**
- **STT for Hinglish**: use `language_code=hi-IN,en-IN` with `format=codemix`. It keeps English in Latin and numbers as words, and the app's own parsers (`app/lang/`) turn the words into numbers, which the project rules require anyway. Do not use `transcribe` with more than one language for any speech that has money in it. If digits are wanted from the API, `hi-IN` + `transcribe` gave a correct "12,000" (one sample). Change the `hinglish` preset or mode in `app/stt_service.py`. Telugu `te-IN,en-IN` + `transcribe` read "పన్నెండు వేల" correctly in the smoke test. Codemix is still the safer default there too, but it has not been tested for Telugu.
- **TTS input for amounts**: with Devanagari in the sentence, both `₹12,000` and `बारह हज़ार रुपये` are spoken correctly. Prefer the words. They come straight from the deterministic formatter, and the read-back is then exactly what was shown. For a Latin-only (Romanised) sentence, write the amount as words ("baarah hazaar rupaye"). The docs say Latin-only text is normalised as English, so "12,000" would be read as "twelve thousand". For Telugu, write the amount as words (పన్నెండు వేలు).
