> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Realtime streaming

> Real-time speech-to-text over a persistent WebSocket connection.

## Overview

Stream raw PCM audio frames and receive transcript segments as speech is detected. The server uses Voice Activity Detection (VAD) to identify speech boundaries and returns a transcript for each segment.

| Use case | Recommended endpoint |
| - | - |
| Live microphone / phone call / real-time audio | **This endpoint** |
| Short pre-recorded clips ≤ 30 s | [STT REST](https://docs.gnani.ai/api/STT/speech-to-text.md) |
| Large files or bulk jobs | [STT Batch](https://docs.gnani.ai/api/STTBatch/Introduction.md) |

> [!NOTE]
>
> **Model:**  Not sure which to use? See [Models](https://docs.gnani.ai/api/STT/models/overview.md).

Streaming details for Prisma v3.0 are in [Prisma v3.0 on streaming](#prisma-v3-0-on-streaming).

***

## Endpoint

```text theme={null}
WSS wss://api.vachana.ai/stt/v3/stream
```

***

## Connection headers

All configuration is passed as WebSocket upgrade headers at connection time. The parameters use the same names as [REST](https://docs.gnani.ai/api/STT/speech-to-text.md) (`language_code`, `model`, `format` and so on), so one set of names works on both. The older spellings (`lang_code`, `x-model`, `x-format`, `x-keyterms` and the rest) are still accepted, so existing integrations keep working. If you send both spellings of one parameter, the new name wins. Most headers are fixed for the life of the connection — reconnect with new headers to change them. The exceptions can be updated mid-session via [`update_settings`](#client-control-frames) control frames, on every model: `language_code`, `format`, `itn_native_numerals` (no effect on Prisma v3.0), the find-and-replace settings (`enable_substitution`, `substitution_map`) and the word-boosting settings (`bias_list`, `bias_score`). On Prisma v3.0 the keyterms list is changed through the `bias` key. `topic`, `previous_text` and `speaker_names` are fixed for the life of the connection.

| Header | Required | Default | Description |
| - | - | - | - |
| `x-api-key-id` | Yes | — | Your Gnani API key. |
| `language_code` | Yes | — | A language code for transcription (see [Supported Languages](#supported-languages)). Prisma v2.5 accepts one language, or `indic-auto` (the language is identified automatically; only Prisma v3.0 returns `detected_language_code`). Prisma v3.0 also accepts `indic-auto`, or a comma-separated list of 1–4 languages such as `hi-IN,en-IN`. The connection closes with an `error` message if it is missing. With `model=prisma-v3.0` and `format=transliterate` it is optional and defaults to `indic-auto`. |
| `model` | No | — | `prisma-v3.0` selects Prisma v3.0 and `prisma-v2.5` selects Prisma v2.5. When omitted, the default model (Prisma v2.5) is used. Any other value is ignored and the default model is used; unlike REST, no error is returned. |
| `keyterms` | No | — | Words or short phrases to favour, as a JSON array or comma-separated, up to 200. JSON-escape non-ASCII text. An invalid value is ignored. Prisma v3.0. See [Context](https://docs.gnani.ai/api/STT/models/prisma-v3.md#context). |
| `topic` | No | — | What the audio is about, as free text. Prisma v3.0 only; ignored by other models. See [Context](https://docs.gnani.ai/api/STT/models/prisma-v3.md#context). |
| `previous_text` | No | — | What was said just before this audio, as free text. Prisma v3.0 only; ignored by other models. |
| `speaker_names` | No | — | Names of the people speaking, as a JSON array or comma-separated, 1–4. Prisma v3.0 only; ignored by other models. |
| `x-idle-timeout-sec` | No | `60` | How long the server waits without detecting speech before it closes the session, in seconds. Accepted range `5`–`900`; values outside it are clamped. Raise it if your callers can be silent for a long time. |
| `x-api-request-id` | No | generated | Your correlation id. |
| `x-sample-rate` | No | `16000` | Sample rate of the audio stream in Hz. Accepted values: `8000`, `16000`, `44100`, `48000`. Must match the actual sample rate of your audio source. |
| `format` | No | `verbatim` | `verbatim` — raw spoken-form output. `transcribe` — number formatting: on Prisma v2.5 this enables Inverse Text Normalization (see [ITN](#inverse-text-normalization-itn)); on Prisma v3.0 the model writes numbers itself. `codemix` (Prisma v3.0 only) — English words stay in Latin script and numbers mostly stay as spoken words. `transliterate` (Prisma v3.0 only) — the whole transcript is written in Latin letters. See [Output style when streaming](https://docs.gnani.ai/api/STT/models/prisma-v3.md#output-style-when-streaming). |
| `itn_native_numerals` | No | `false` | Prisma v2.5. When `format=transcribe`, set `true` to render digits in the native script of the target language (e.g. `₹५,०००` instead of `₹5,000` for Hindi). No effect on Prisma v3.0: the model writes numbers itself. |
| `enable_substitution` | No | `false` | Set to `true` to enable post-transcription find-and-replace. All patterns in `substitution_map` are applied to each transcript segment after ITN. Can be toggled mid-session via `update_settings`. |
| `substitution_map` | No | — | JSON-encoded list of substitution rules (same format as the REST `substitution_map` field). Only evaluated when `enable_substitution=true`. Maximum 10 rules. Can be replaced mid-session via `update_settings`. See [Find-and-Replace](#find-and-replace-substitution-1) below. |
| `bias_list` | No | — | Words to boost during recognition (word boosting). JSON array or comma-separated; up to 100 single words, letters only. Requires `bias_score`. Can be replaced mid-session via `update_settings`. See [Word Boosting](#word-boosting). Prisma v2.5; on Prisma v3.0 `bias_list` is the older name of `keyterms` and is used only when `keyterms` is not sent. |
| `bias_score` | No | — | Boost strength: `0.0`, `0.5`, `1.0`, `1.5` or `2.0`. `0.0` or omitted disables boosting. Prisma v2.5 only; ignored by Prisma v3.0. |

**Choosing the right sample rate:**

| Value | When to use |
| - | - |
| `48000` | Browser `getUserMedia` default; Mac microphone |
| `44100` | Mac microphone alternate; CD-quality audio |
| `16000` | Wideband telephony; sent as-is with no resampling |
| `8000` | Narrowband telephony (legacy PSTN / VoIP) |

### VAD tuning headers

These five optional headers control **where speech starts and stops**. Defaults are tuned
for a clean wideband microphone — override them for telephony, noisy environments, or
latency-sensitive flows. See [VAD Tuning](#voice-activity-detection-vad-tuning) for
guidance and ready-made presets.

| Header | Required | Default | Range | Description |
| - | - | - | - | - |
| `x-vad-threshold` | No | `0.7` | `0.0`–`1.0` | Speech-probability threshold. Clean mic: `0.45`–`0.55`. Telephony: `0.65`–`0.75`. |
| `x-min-silence-ms` | No | `500` | `100`–`2000` | Silence required to close a segment. Telephony: `400`–`600`. Conversation: `600`–`900`. |
| `x-min-speech-ms` | No | `100` (`200` at 8 kHz) | `50`–`2000` | Speech required to open a segment. Raise in noisy environments. |
| `x-min-segment-ms` | No | `120` | `100`–`1000` | Floor on the speech needed to confirm a segment. Raise to `200`–`300` to suppress stray sounds. |
| `x-max-speech-s` | No | disabled | `5.0`–`120.0` | Hard cap on a single segment. Set (e.g. `30`) to force transcripts on monologues. |

***

## Voice activity detection (VAD) tuning

VAD is what turns a continuous audio stream into discrete utterances. It listens for the
moment speech **starts**, holds the segment open through natural pauses, and closes it when
the speaker stops. Every closed segment becomes exactly one `transcript` message — so VAD
settings directly control both **how your transcripts are chunked** and **how quickly they
arrive**.

> [!NOTE]
>
> VAD headers are **fixed for the life of the connection**. To change them, close the
> WebSocket and reconnect with the new values.

### The two knobs that matter most

Most tuning comes down to two trade-offs:

| Goal | Change | Trade-off |
| - | - | - |
| **Faster transcripts** | Lower `x-min-silence-ms` | A sentence may split at a natural pause |
| **More complete sentences** | Raise `x-min-silence-ms` | Every transcript arrives later |
| **Fewer false triggers** (noise, keyboard, hold music) | Raise `x-vad-threshold` and `x-min-speech-ms` | Soft or distant speech may be missed |
| **Catch quiet speakers** | Lower `x-vad-threshold` | Background noise may open segments |

### Header reference

#### `x-vad-threshold`

**How confident the model must be that a frame contains speech.** Type `float`, default
`0.7`, range `0.0`–`1.0`.

* **Higher** (`0.75`+) — stricter. Rejects background noise, hold music, and line hiss, but
  may miss soft or distant speech.
* **Lower** (`0.45`–`0.55`) — more sensitive. Catches quiet speakers and whispers, but noise
  is more likely to open a segment.

| Environment | Suggested value |
| - | - |
| Clean headset or studio mic | `0.45`–`0.55` |
| Open office / laptop mic | `0.6`–`0.7` |
| Telephony, call centre, noisy line | `0.65`–`0.75` |

#### `x-min-silence-ms`

**How much silence must follow speech before the segment is closed and transcribed.** Type
`integer`, default `500`, range `100`–`2000`.

This is the single biggest lever on **end-of-utterance latency** — the transcript cannot
arrive until this timer expires.

* **Lower** (`300`–`400`) — snappier results. Best for IVR prompts and short commands, but a
  speaker who pauses mid-sentence ("my number is… 98765…") will get two transcripts instead
  of one.
* **Higher** (`700`–`900`) — more complete utterances. Best for natural conversation and
  dictation, at the cost of \~half a second of extra latency per turn.

| Use case | Suggested value |
| - | - |
| IVR / short commands / yes-no answers | `300`–`400` |
| Telephony conversation | `400`–`600` |
| Natural conversation, dictation, meetings | `600`–`900` |

#### `x-min-speech-ms`

**How much consecutive speech is needed before a segment is opened.** Type `integer`,
default `100` (`200` when `x-sample-rate: 8000`), range `50`–`2000`.

Acts as a noise gate at the *start* of speech. A door slam, a click, or a cough is shorter
than this window, so it never opens a segment and never costs you a transcription.

* **Raise** (`200`–`300`) in noisy environments or on noisy telephony lines.
* **Lower** (`50`–`80`) only if you are losing very short interjections like "haan" or
  "yes".

#### `x-min-segment-ms`

**A floor on the amount of speech required to confirm a segment.** Type `integer`, default
`120`, range `100`–`1000`.

This works together with `x-min-speech-ms` — whichever demands more speech wins. Because it
applies at the *start* of a segment, audio below this threshold never opens a segment at
all, so no `transcript` message is produced for it.

* **Raise** to `200`–`300` to suppress residual coughs, breaths, and line pops that survive
  the `x-min-speech-ms` gate.
* **Leave at the default** (or lower toward `100`) if you expect genuine one-word answers
  like "yes", "नहीं", or "two".

> [!WARNING]
>
> Raising `x-min-segment-ms` too far silently drops short answers — they produce no
> `transcript` message at all. If users report that "yes"/"no" responses never come back,
> this header is the first thing to check.

#### `x-max-speech-s`

**Hard cap on how long a single segment can run.** Type `float`, **disabled by default**,
range `5.0`–`120.0`.

Normally a segment closes when the speaker pauses. If someone talks continuously — reading
an address, giving a monologue — that pause may never come, and you get no transcript until
they stop. Setting this header force-closes and transcribes the segment at the cap so
results keep flowing.

* **Leave unset** for normal turn-taking conversation.
* **Set to `20`–`30`** for monologue-heavy audio (voicemail, dictation, long narration) to
  get steady intermediate results.

> [!NOTE]
>
> The overall session is always capped at **15 minutes** regardless of this setting.
> `x-max-speech-s` bounds a single uninterrupted segment *within* that session.

### Presets

Copy-paste starting points. Tune from here rather than from scratch.

```text Clean web microphone (48 kHz) theme={null}
x-api-key-id:      <your-api-key>
language_code:        en-IN
x-sample-rate:     48000
x-vad-threshold:   0.5
x-min-silence-ms:  700
```

```text Telephony / call centre (8 kHz) theme={null}
x-api-key-id:      <your-api-key>
language_code:        hi-IN
x-sample-rate:     8000
x-vad-threshold:   0.7
x-min-speech-ms:   200
x-min-silence-ms:  500
```

```text IVR / short commands theme={null}
x-api-key-id:      <your-api-key>
language_code:        en-IN
x-sample-rate:     8000
x-min-silence-ms:  300
x-min-speech-ms:   100
x-min-segment-ms:  100
```

```text Monologue / dictation theme={null}
x-api-key-id:      <your-api-key>
language_code:        en-IN
x-sample-rate:     16000
x-min-silence-ms:  800
x-max-speech-s:    30
```

### Setting VAD headers in code

VAD headers are sent at connection time, alongside your API key.

```python Python (websockets) theme={null}
import asyncio
import websockets

headers = {
    "x-api-key-id":     "your-api-key",
    "language_code":        "hi-IN",
    "x-sample-rate":    "8000",
    "x-vad-threshold":  "0.7",
    "x-min-speech-ms":  "200",
    "x-min-silence-ms": "500",
}

async def main():
    async with websockets.connect(
        "wss://api.vachana.ai/stt/v3/stream",
        additional_headers=headers,   # `extra_headers` on websockets < 13
    ) as ws:
        ...                           # send audio and read frames here

asyncio.run(main())
```

```javascript Node.js (ws) theme={null}
import WebSocket from "ws";

const ws = new WebSocket("wss://api.vachana.ai/stt/v3/stream", {
  headers: {
    "x-api-key-id": "your-api-key",
    "language_code": "hi-IN",
    "x-sample-rate": "8000",
    "x-vad-threshold": "0.7",
    "x-min-speech-ms": "200",
    "x-min-silence-ms": "500",
  },
});
```

> [!NOTE]
>
> Browser `WebSocket` cannot set custom headers. From a browser, proxy the connection
> through your own backend and attach the headers there — this also keeps your API key off
> the client.

> [!WARNING]
>
> The Python SDK (`gnani-vachana`) does not currently expose VAD tuning. Use a raw
> WebSocket client, as above, if you need these headers.

***

## Connection flow

A WebSocket session follows a strict sequence:

1. **Client connects** — opens a WebSocket to `/stt/v3/stream` with all required headers.
2. **Server confirms** — immediately sends a `connected` message echoing the active configuration.
3. **Client streams audio** — continuously sends binary frames of raw PCM audio at a steady real-time cadence.
4. **Server detects speech** — VAD identifies end-of-speech boundaries and emits a `processing` message to acknowledge that a segment was captured.
5. **Server returns transcript** — sends a `transcript` message with the transcribed text, segment metadata, and latency.
6. **Either side closes** — client or server may close the connection at any time.

> [!NOTE]
>
> The `processing` message is a low-latency signal that audio was captured and transcription has begun. Expect a `transcript` message shortly after.

***

## Audio format & sending audio

All audio must be sent as **raw PCM binary frames** over the WebSocket. No container format (WAV, MP3, etc.) is accepted mid-stream.

### PCM specification

| Property | 16 kHz | 8 kHz |
| - | - | - |
| Encoding | PCM signed 16-bit little-endian | PCM signed 16-bit little-endian |
| Sample Rate | 16,000 Hz | 8,000 Hz |
| Channels | 1 (mono) | 1 (mono) |
| Samples per chunk | 512 | 512 |
| **Bytes per frame** | **1,024 bytes** (512 samples × 2 bytes) | **1,024 bytes** (512 samples × 2 bytes) |
| Frame duration | 32 ms | 64 ms |

### Sending rules

* Each binary frame must be **exactly 1,024 bytes**.
* Frames must be sent at **real-time cadence** — one frame every 32 ms (16 kHz) or 64 ms (8 kHz). Do not buffer and burst; this degrades VAD accuracy.
* For `44100` and `48000` Hz sources, the server resamples internally — still send 1,024-byte frames at the appropriate cadence.

***

## Server messages

The server sends JSON text frames. All messages share a `type` discriminator field and an ISO-8601 `timestamp`.

### `connected`

Sent once immediately after the WebSocket handshake succeeds.

```json theme={null}
{
  "type": "connected",
  "message": "STT service ready — VAD service connected",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "config": {
    "sample_rate": 16000,
    "chunk_size": 512
  }
}
```

| Field | Type | Description |
| - | - | - |
| `type` | `string` | Always `"connected"`. |
| `message` | `string` | Human-readable status string. |
| `timestamp` | `string` | ISO-8601 server timestamp. |
| `config.sample_rate` | `integer` | Active sample rate in Hz, echoed from `x-sample-rate`. |
| `config.chunk_size` | `integer` | Expected chunk size in samples (always 512). |

With Prisma v3.0 the message also carries `request_id` and more `config` keys:

```json theme={null}
{
  "type": "connected",
  "message": "STT service ready — VAD service connected",
  "request_id": "122d91d1-dd1d-4e51-8b53-a6979b710272",
  "config": {
    "sample_rate": 16000,
    "chunk_size": 512,
    "language_code": "indic-auto",
    "format": "verbatim",
    "language_candidates": ["hi", "en"]
  },
  "timestamp": "2026-10-22T12:36:50.123Z"
}
```

| Field | Type | Description |
| - | - | - |
| `request_id` | `string` | Your `x-api-request-id`, or a generated id. |
| `config.language_code` | `string` | Active language code. |
| `config.format` | `string` | Active format. |
| `config.language_candidates` | `string[]` | Only when you send a list of languages. |

### `processing`

Emitted when VAD detects the end of a speech segment and transcription has begun. Use this as a low-latency acknowledgment that audio was captured.

```json theme={null}
{
  "type": "processing",
  "timestamp": "2024-01-15T10:30:05.123Z"
}
```

| Field | Type | Description |
| - | - | - |
| `type` | `string` | Always `"processing"`. |
| `timestamp` | `string` | ISO-8601 timestamp when speech-end was detected. |

### `transcript`

Contains the transcribed text for a completed speech segment.

```json theme={null}
{
  "type": "transcript",
  "timestamp": "2024-01-15T10:30:05.987Z",
  "text": "Hello, how are you today?",
  "audio_duration_ms": 2340,
  "segment_id": "<segment_id>",
  "segment_index": 1,
  "latency": 320
}
```

| Field | Type | Description |
| - | - | - |
| `type` | `string` | Always `"transcript"`. |
| `timestamp` | `string` | ISO-8601 timestamp when the transcript was emitted. |
| `text` | `string` | Transcribed text. Format depends on the `format` header. |
| `audio_duration_ms` | `integer` | Duration of the captured speech segment in milliseconds. |
| `segment_id` | `string` | Unique identifier for this speech segment, in the form `<request_id>-seg-<N>`. Use for deduplication or support correlation. |
| `segment_index` | `integer` | 1-based position of this segment within the session. The first segment is `1`. |
| `latency` | `integer` | Time in milliseconds taken to transcribe this segment. |
| `detected_language_code` | `string` | Prisma v3.0. Judged per utterance from the script of its text, for every session. Absent for empty text, and not sent in an `format=transliterate` session. |
| `output.literal` | `string` | Prisma v2.5 only. The text before number formatting (ITN). Sent whenever number formatting ran, including when it left the text unchanged, in which case it equals `text`. Not returned by Prisma v3.0. |
| `utterance_id` | `string` | Identifies the utterance this transcript belongs to. Sent for every model. |
| `is_final` | `boolean` | Always `true` on a `transcript`. Sent for every model. |

```json theme={null}
{
  "type": "transcript",
  "text": "ఈ రోజు మీటింగ్ చాలా ముఖ్యం",
  "detected_language_code": "te-IN",
  "audio_duration_ms": 2340.0,
  "segment_id": "122d91d1-seg-1",
  "segment_index": 1,
  "latency": 380,
  "timestamp": "2026-10-22T12:36:53.400Z"
}
```

### `speech_start`

Sent when voice is detected. On Prisma v3.0 it also carries `utterance_id`.

### `error`

Sent when the server encounters a recoverable or fatal error. The connection may remain open after a recoverable error.

| Field | Type | Description |
| - | - | - |
| `type` | `string` | Always `"error"`. |
| `timestamp` | `string` | ISO-8601 timestamp of the error. |
| `message` | `string` | Human-readable description of the error. |

```json theme={null}
{
  "type": "error",
  "timestamp": "2024-01-15T10:30:10.000Z",
  "message": "STT engine failed to initialize"
}
```

When the connection closes after an `error` message:

| Situation | What happens |
| - | - |
| Failure on a single utterance | `error` message; the session stays open. |
| Bad handshake header (`language_code` missing or invalid, bad `format`) | `error` message, then the connection closes with code `1008`. |
| Bad `substitution_map` | The connection closes with code `1008` and the reason `Invalid x-substitution-map`, without an `error` message. |
| Missing or invalid API key | The handshake is refused with HTTP `401` (see [Authentication and rate limits](https://docs.gnani.ai/api/introduction/errors.md#authentication-and-rate-limits)); no WebSocket opens. |
| Session longer than 15 minutes | `error` message, then the connection closes with code `1001`. |
| Concurrent-session cap reached | The connection is rejected with an `error` message naming the limit. |

See [Error Reference](https://docs.gnani.ai/api/introduction/errors.md) for all Speech API errors.

### `settings_updated`

Sent in response to a successful `update_settings` control frame. Echoes the full active configuration after the update.

```json theme={null}
{
  "type": "settings_updated",
  "timestamp": "2024-01-15T10:31:00.000Z",
  "config": {
    "language_code": "en-IN",
    "format": "verbatim",
    "itn_native_numerals": false,
    "substitution_enabled": true,
    "bias_word_count": 2,
    "bias_score": 1.5
  }
}
```

| Field | Type | Description |
| - | - | - |
| `type` | `string` | Always `"settings_updated"`. |
| `timestamp` | `string` | ISO-8601 timestamp of the update. |
| `config.language_code` | `string` | Active language code. |
| `config.format` | `string` | Active format (`verbatim` or `transcribe`; `codemix` and `transliterate` on Prisma v3.0). |
| `config.itn_native_numerals` | `boolean` | Whether native numeral rendering is on. |
| `config.substitution_enabled` | `boolean` | Whether find-and-replace is currently active. |
| `config.bias_word_count` | `integer` | Number of words currently boosted (`0` when word boosting is off). |
| `config.bias_score` | `number` | Active boost strength. |

***

## Client control frames

Alongside binary PCM audio frames, the client can send **JSON text frames** to update settings mid-session. No reconnect needed.

### `update_settings`

Send a JSON text frame with `"type": "update_settings"` and the settings you want to change. Unspecified fields keep their current values.

```json theme={null}
{"type": "update_settings", "substitution": {"enabled": true, "map": [{"patterns": ["ok", "okay"], "replacement": "acknowledged"}]}}
```

#### Substitution key

| Key | Type | Description |
| - | - | - |
| `substitution.enabled` | `boolean` | Toggle find-and-replace on or off for subsequent segments. |
| `substitution.map` | `array` | Replace the full rule set. Uses the same format as `substitution_map`. Ignored when `enabled` is `false`. |

You can send `enabled` and `map` together or separately:

```json theme={null}
// Turn on with a new rule set
{"type": "update_settings", "substitution": {"enabled": true, "map": [{"patterns": ["hello", "hi"], "replacement": "greetings"}]}}

// Turn off without changing the stored rule set
{"type": "update_settings", "substitution": {"enabled": false}}

// Swap the rule set while already on
{"type": "update_settings", "substitution": {"map": [{"patterns": ["bye", "goodbye"], "replacement": "farewell"}]}}
```

#### Bias key

| Key | Type | Description |
| - | - | - |
| `bias.list` | `array` \| `string` | Replace the boosted words (JSON array or comma-separated string). `[]` or `null` turns word boosting off. |
| `bias.score` | `number` | New boost strength: `0.0`, `0.5`, `1.0`, `1.5` or `2.0`. |

Omit a key to keep its current value — for example `{"bias": {"score": 2.0}}` changes only the strength.

```json theme={null}
{"type": "update_settings", "bias": {"list": ["Vachana", "EMI"], "score": 1.5}}
```

The change applies from the **next** speech segment. An invalid update is ignored as a whole and the previous settings stay in effect.

The server replies with a `settings_updated` frame confirming the new state.

The frame can also carry these keys, on any model (`format` accepts only the values the model supports):

```json theme={null}
{"type": "update_settings", "language_code": "ta-IN", "format": "transcribe", "itn_native_numerals": false, "bias": {"list": ["Vachana", "HDFC"], "score": 1.0}, "substitution": {"enabled": false}}
```

VAD settings are fixed at connection time and are rejected if you try to change them.

### `commit`

Closes the open utterance immediately instead of waiting for silence. Works on every model.

```json theme={null}
{"type": "commit"}
```

***

## Prisma v3.0 on streaming

Select Prisma v3.0 with the `model=prisma-v3.0` header. Everything else you send today keeps working.

### Language list

* `language_code: hi-IN` → the model listens for Hindi first.
* `language_code: hi-IN,en-IN` → the model listens for Hindi and English first. The list is a hint, not a lock.
* `language_code: indic-auto` → the model identifies the language itself.
* A language the model does not cover, or more than four → an `error` message, then the connection closes.
* Changing `language_code` with `update_settings` **ends** the list of languages (`language_candidates`) for the session.

### Output style

Streaming supports `verbatim`, `transcribe`, `codemix` and `transliterate`. The model writes the style you ask for, exactly as it does on REST, so a `transcribe` session returns the same text as REST. There is no separate number-formatting step, so `itn_native_numerals` has no effect and `output.literal` is not returned. The style you get when you omit `format` is in [Output style when streaming](https://docs.gnani.ai/api/STT/models/prisma-v3.md#output-style-when-streaming).

With `format=transliterate` the whole transcript is written in Latin letters (for example `तो ठीक है` becomes `to theek hai`). `language_code` is optional and defaults to `indic-auto`, a list of languages is ignored, and `detected_language_code` is not sent. `update_settings` can switch into and out of it, and the session's own language applies again when you leave it. See [Romanised output](https://docs.gnani.ai/api/STT/models/prisma-v3.md#romanised-output-transliterate).

### Context

`keyterms`, `topic`, `previous_text` and `speaker_names` are sent as connection headers with the same names and rules as REST, and apply to every utterance in the session. See [Context](https://docs.gnani.ai/api/STT/models/prisma-v3.md#context). `multi_lang_codes` is not accepted on streaming.

### Session limits

| Limit | Value |
| - | - |
| Session length | 15 minutes, then an `error` message and close code `1001` |
| Idle (no speech segment) | 60 s by default; set `x-idle-timeout-sec` (5–900) |
| Concurrent sessions | Per-organisation cap; a rejected connection gets an `error` message naming the limit |
| Invalid handshake header | `error` message, then close code `1008` |

### Example (Python)

```python theme={null}
import asyncio, json, websockets

HEADERS = {
    "x-api-key-id": "<API_KEY>",
    "model": "prisma-v3.0",
    "language_code": "hi-IN,en-IN",   # or "indic-auto", or one language
    "x-sample-rate": "16000",
}

async def run(pcm_chunks):
    async with websockets.connect(
        "wss://api.vachana.ai/stt/v3/stream",
        additional_headers=HEADERS,            # `extra_headers` on websockets < 13
    ) as ws:
        async def send():
            for chunk in pcm_chunks:           # 16-bit mono PCM bytes
                await ws.send(chunk)
                await asyncio.sleep(0.1)
            await ws.send(json.dumps({"type": "commit"}))

        async def receive():
            async for raw in ws:
                frame = json.loads(raw)
                kind = frame["type"]
                if kind == "transcript":
                    print(frame.get("detected_language_code"), frame["text"])
                elif kind == "error":
                    print("error:", frame["message"])

        await asyncio.gather(send(), receive())

# asyncio.run(run(pcm_chunks))   # pcm_chunks: an iterable of 16-bit mono PCM byte chunks
```

***

## Python SDK

The official Python SDK wraps the WebSocket connection, audio pacing, and event parsing into a clean async interface.

### Installation

```bash theme={null}
pip install gnani-vachana
```

Requires **Python 3.10+**.

### Authentication

The streaming client requires your API key and language code.

```python Constructor argument theme={null}
from gnani.stt import GnaniSTTStreamClient

stream = GnaniSTTStreamClient(
    api_key="your-api-key",
    language_code="hi-IN",
)
```

```bash Environment variable theme={null}
export GNANI_API_KEY="your-api-key"
```

```python Environment variable (usage) theme={null}
from gnani.stt import GnaniSTTStreamClient

# Picks up GNANI_API_KEY from environment automatically
stream = GnaniSTTStreamClient(language_code="hi-IN")
```

### Stream audio from a file

Use the async context manager and the `stream_audio` helper. It handles real-time pacing automatically so frames are sent at the correct cadence for VAD.

```python theme={null}
import asyncio
from gnani.stt import GnaniSTTStreamClient

async def main():
    async with GnaniSTTStreamClient(
        api_key="your-api-key",
        language_code="hi-IN",
        sample_rate=16000,
    ) as stream:
        with open("audio.pcm", "rb") as f:
            transcripts = await stream.stream_audio(
                f,
                on_transcript=lambda t: print(f"Transcript: {t.text}"),
                on_processing=lambda p: print("Processing..."),
                realtime_pace=True,  # sends frames at real-time cadence
            )

    print(f"Total segments: {len(transcripts)}")

asyncio.run(main())
```

> [!NOTE]
>
> The last sentence is only transcribed once the speaker stops talking. If the file ends mid-speech, `stream_audio` returns without it; end recordings with about a second of silence.

### Iterate over events manually

For lower-level control — handling each event type differently or interleaving sending and receiving — iterate over the stream directly.

```python theme={null}
import asyncio
from gnani.stt import GnaniSTTStreamClient, StreamTranscriptEvent, StreamProcessingEvent

async def main():
    async with GnaniSTTStreamClient(
        api_key="your-api-key",
        language_code="hi-IN",
    ) as stream:
        with open("audio.pcm", "rb") as f:
            while chunk := f.read(1024):
                await stream.send_audio(chunk)
                await asyncio.sleep(0.032)  # 32 ms per frame at 16 kHz

        # 1 s of silence, so the last sentence is detected as finished
        await stream.send_audio(bytes(32000))

        async for event in stream:
            if isinstance(event, StreamTranscriptEvent):
                print(f"[Segment {event.segment_index}] {event.text}")
                print(f"  Duration: {event.audio_duration_ms} ms  Latency: {event.latency} ms")
                break  # stop after the first transcript; remove `break` to keep listening
            elif isinstance(event, StreamProcessingEvent):
                print("Processing speech...")

asyncio.run(main())
```

> [!NOTE]
>
> A transcript is sent when the speaker stops talking. If your audio ends while someone is still speaking, the last sentence is not finalised; end the audio with about a second of silence (as above). The event stream stays open until you close the connection, so stop reading when you have what you need.

### Using 8 kHz audio (telephony)

```python theme={null}
stream = GnaniSTTStreamClient(
    api_key="your-api-key",
    language_code="en-IN",
    sample_rate=8000,
)
```

### SDK event types

All events are typed dataclasses with a `raw` field containing the full server JSON.

| Event class | Key fields | Description |
| - | - | - |
| `StreamConnectedEvent` | `message`, `sample_rate`, `chunk_size` | Sent once after the WebSocket handshake. Confirms the active config. |
| `StreamProcessingEvent` | `timestamp` | VAD detected end-of-speech; transcription has started. |
| `StreamTranscriptEvent` | `text`, `segment_index`, `audio_duration_ms`, `latency` | Completed transcript for a speech segment. |
| `StreamErrorEvent` | `message`, `timestamp` | Server-side error, recoverable or fatal. |

### Error handling

```python theme={null}
from gnani.stt import (
    StreamConnectionError,  # Could not establish the WebSocket connection
    StreamClosedError,      # Attempted to send on an already-closed stream
    StreamError,            # Server returned an error message mid-session
)

try:
    async with GnaniSTTStreamClient(api_key="your-api-key") as stream:
        await stream.send_audio(chunk)
except StreamConnectionError as e:
    print(f"Could not connect: {e}")
except StreamClosedError as e:
    print(f"Stream was already closed: {e}")
except StreamError as e:
    print(f"Server error: {e.message} (at {e.timestamp})")
```

***

## Supported languages

| Language | Code | Native Script | Example |
| - | - | - | - |
| Bengali | `bn-IN` | Bengali (বাংলা) | "আমি ভাত খাই" |
| English | `en-IN` | English (Latin) (Accepts English-Hindi mixed audio and generates output in English (Latin script).) | "I am going to the market" |
| Gujarati | `gu-IN` | Gujarati (ગુજરાતી) | "હું બજાર જાઉં છું" |
| Hindi | `hi-IN` | Devanagari (हिन्दी) | "मैं बाज़ार जा रहा हूँ" |
| Kannada | `kn-IN` | Kannada (ಕನ್ನಡ) | "ನಾನು ಮಾರುಕಟ್ಟೆಗೆ ಹೋಗುತ್ತೇನೆ" |
| Malayalam | `ml-IN` | Malayalam (മലയാളം) | "ഞാൻ ചന്തയിലേക്ക് പോകുന്നു" |
| Marathi | `mr-IN` | Devanagari (मराठी) | "मी बाजारात जातोय" |
| Punjabi | `pa-IN` | Gurmukhi (ਪੰਜਾਬੀ) | "ਮੈਂ ਬਾਜ਼ਾਰ ਜਾ ਰਿਹਾ ਹਾਂ" |
| Tamil | `ta-IN` | Tamil (தமிழ்) | "நான் சந்தைக்கு செல்கிறேன்" |
| Telugu | `te-IN` | Telugu (తెలుగు) | "నేను మార్కెట్‌కి వెళ్తున్నాను" |

> [!NOTE]
>
> **`indic-auto` (Prisma v3.0 only).** Send `language_code=indic-auto` to let the model identify the language itself. It is not a language: the reply carries the language it heard in `detected_language_code`. See [Language detection](https://docs.gnani.ai/api/STT/models/prisma-v3.md#language-detection).

***

## Inverse text normalization (ITN)

> [!NOTE]
>
> This section describes **Prisma v2.5**. On Prisma v3.0 the model writes numbers itself, so there is no separate ITN step, `itn_native_numerals` has no effect and `output.literal` is not returned. See [Output style when streaming](https://docs.gnani.ai/api/STT/models/prisma-v3.md#output-style-when-streaming).

When `format=transcribe` is set, ITN runs on every transcript segment immediately after recognition — converting spoken-form numbers, currency, dates, times, and phone numbers into the compact written form a reader expects.

### What ITN normalizes

#### 1 — Cardinal & ordinal numbers

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| दो हज़ार | 2,000 | Indian comma grouping |
| पाँच लाख बीस हज़ार | 5,20,000 | Lakh-scale grouping |
| five lakh | 5,00,000 | English lakh convention |
| पहला / twenty first | 1st / 21st | Ordinal suffix |

#### 2 — Currency & money

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| पाँच सौ रुपये | ₹500 | ₹ + amount |
| तीन रुपये पचास पैसे | ₹3.50 | ₹ + rupees.paise |
| I need five thousand rupees | ₹5,000 | English India pipeline |
| pay do lakh rupees | ₹2,00,000 | Code-mixed en/hi |

#### 3 — Dates

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| बीस जनवरी दो हज़ार पच्चीस | 20 जनवरी 2025 | DD Month YYYY (hi) |
| fifteenth january twenty twenty five | 15th January 2025 | Ordinal Month YYYY (en) |

#### 4 — Times

Indian time-of-day words (सुबह, दोपहर, शाम, रात) automatically map to 24-hour HH:MM output.

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| सुबह पाँच बजे | सुबह 05:00 | सुबह = AM |
| शाम पाँच बजे | शाम 17:00 | शाम = evening (16–20 h) |
| रात के दस बजे | रात 22:00 | रात = night (20–24 h) |
| meeting at five fifteen in the evening | meeting 17:15 in the evening | en — 24-hour |

#### 5 — Phone numbers & PIN codes

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| नौ आठ सात छह पाँच चार तीन दो एक शून्य | 9876543210 | 10 digits → phone |
| एक एक शून्य शून्य शून्य एक | 110001 | 6 digits → PIN |
| one two three four five six | 123456 | English digit words |

#### 6 — Mixed & code-mixed utterances

| Spoken input (ASR) | Written output (ITN) |
| - | - |
| कल थ्री फिफ्टी पीएम को पाँच सौ रुपये transfer करना है | कल 15:50 को ₹500 transfer करना है |
| pay do lakh rupees by fifteenth march | pay ₹2,00,000 by 15th March |

### Native script digits — `itn_native_numerals`

By default, ITN outputs Western Arabic digits (0–9). Set `itn_native_numerals: true` in the connection headers to render digits in the native script of the target language.

| Language | Spoken input | `false` (default) | `true` — native script |
| - | - | - | - |
| Hindi `hi-IN` | पाँच हज़ार रुपये | ₹5,000 | ₹५,००० |
| English `en-IN` | five thousand rupees | ₹5,000 | ₹5,000 (Latin — no change) |

### What ITN does not change

ITN intentionally preserves idiomatic and ambiguous phrases to avoid incorrect normalization.

* **दो तीन** (meaning *a few*) stays as text, not `2` or `3`
* **कर दो / ले दो** (imperative verbs) are kept as words, not treated as cardinal 2

***

## Find-and-replace (substitution)

After transcription (and after ITN, if enabled), the server can apply a custom set of find-and-replace rules to every `transcript` segment before delivering it to your client. Use this to:

* Normalise domain-specific terms ("rs" → "INR", "ok" → "acknowledged")
* Replace competitor names, internal codes, or product shortforms
* Standardise phrases the model transcribes differently from your expected output

### Enable at connection time

Pass `enable_substitution:   true` and your rules in `substitution_map` as part of the WebSocket upgrade headers.

```text Headers theme={null}
x-api-key-id:          <your-api-key>
language_code:            en-IN
enable_substitution:   true
substitution_map:      [{"patterns":["okay","ok"],"replacement":"acknowledged"},{"patterns":["rupees","rs"],"replacement":"INR"}]
```

```python Python (websockets) theme={null}
import asyncio, websockets, json

rules = json.dumps([
    {"patterns": ["okay", "ok", "alright"], "replacement": "acknowledged"},
    {"patterns": ["rupees", "rs"],           "replacement": "INR"},
])

headers = {
    "x-api-key-id":          "your-api-key",
    "language_code":             "en-IN",
    "enable_substitution": "true",
    "substitution_map":    rules,
}

async def main():
    async with websockets.connect(
        "wss://api.vachana.ai/stt/v3/stream",
        additional_headers=headers,
    ) as ws:
        ...                           # send audio and read frames here

asyncio.run(main())
```

```javascript Node.js (ws) theme={null}
import WebSocket from "ws";

const rules = JSON.stringify([
  { patterns: ["okay", "ok"], replacement: "acknowledged" },
  { patterns: ["rupees", "rs"], replacement: "INR" },
]);

const ws = new WebSocket("wss://api.vachana.ai/stt/v3/stream", {
  headers: {
    "x-api-key-id":          "your-api-key",
    "language_code":             "en-IN",
    "enable_substitution": "true",
    "substitution_map":    rules,
  },
});
```

### Toggle mid-session

Send an `update_settings` control frame at any time to turn substitution on/off or swap the rule set — no reconnect needed.

```json theme={null}
{"type": "update_settings", "substitution": {"enabled": true, "map": [{"patterns": ["hello", "hi"], "replacement": "greetings"}]}}
```

See [Client Control Frames](#client-control-frames) for the full reference.

### Rule format

```json theme={null}
[
  {"patterns": ["find1", "find2"], "replacement": "replacement1"},
  {"patterns": ["find3"],          "replacement": "replacement2"}
]
```

* Maximum **10 rules** per session.
* Matching is **case-insensitive** and respects **Unicode word boundaries** — `"ok"` matches `"OK"` but not `"okay"`.
* Longer phrases take priority — `"New Delhi"` is tried before `"Delhi"`.
* Rules are applied in a **single pass** with no cascading.

> [!NOTE]
>
> Substitution runs on the **final client-visible transcript only**. Billing records always carry the original raw transcript.

***

## Word boosting

This section describes Prisma v2.5. For Prisma v3.0 use the `keyterms` header; see [Context](https://docs.gnani.ai/api/STT/models/prisma-v3.md#context).

Word boosting nudges the recognizer toward specific words — brand names, product names, domain terms — so they are more likely to be transcribed correctly. It affects recognition itself and is separate from [find-and-replace](#find-and-replace-substitution-1).

### Enable at connection time

Send `bias_list` and `bias_score` in the WebSocket upgrade headers. Both are needed for boosting to take effect.

```text Headers theme={null}
x-api-key-id:  <your-api-key>
language_code:    hi-IN
format:         verbatim
bias_list:     ["Prisma","EMI"]
bias_score:    1.0
```

```python Python (websockets) theme={null}
import asyncio, websockets, json

headers = {
    "x-api-key-id": "your-api-key",
    "language_code":    "hi-IN",
    "format":     "verbatim",
    "bias_list":  json.dumps(["Prisma", "EMI"]),
    "bias_score": "1.0",
}

async def main():
    async with websockets.connect(
        "wss://api.vachana.ai/stt/v3/stream",
        additional_headers=headers,
    ) as ws:
        ...                           # send audio and read frames here

asyncio.run(main())
```

```javascript Node.js (ws) theme={null}
import WebSocket from "ws";

const ws = new WebSocket("wss://api.vachana.ai/stt/v3/stream", {
  headers: {
    "x-api-key-id": "your-api-key",
    "language_code": "hi-IN",
    "format": "verbatim",
    "bias_list": JSON.stringify(["Prisma", "EMI"]),
    "bias_score": "1.0",
  },
});
```

The list and score apply to **every transcript segment** in the session.

### Change it mid-session

Send an `update_settings` frame to replace the words or strength without reconnecting — see [Client Control Frames](#client-control-frames).

```json theme={null}
{"type": "update_settings", "bias": {"list": ["Vachana", "EMI"], "score": 1.5}}
```

### Rules

| | |
| - | - |
| **Words** | Up to **100**; each a **single word of letters only** (English or supported Indian scripts). No spaces, digits, punctuation, or symbols. Casing doesn't matter. |
| **Score** | `0.0`, `0.5`, `1.0`, `1.5`, `2.0`. Start at `1.0`. `0.0` or omitted = off. |
| **Format** | Use `format=verbatim`; boost words are spoken-form tokens. |
| **Languages** | Works with a specific `language_code` (e.g. `hi-IN`, `en-IN`) on Prisma v2.5, the default model. |

> [!WARNING]
>
> Invalid word-boosting input never rejects the connection or returns an error. If any entry breaks the rules, or the score is not an allowed value, boosting is skipped and audio is transcribed normally. Mid-session, an invalid `update_settings` is ignored and the previous list stays active.

### Indic words in a header

HTTP headers are bytes, and many WebSocket clients refuse or garble non-ASCII values. The portable way is a JSON array with `\u` escapes, which is plain ASCII:

```text theme={null}
bias_list: ["\u0928\u092e\u0938\u094d\u0924\u0947","Vachana"]
```

Raw UTF-8 header bytes are also accepted if your client can send them.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.