> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Error Reference

> Error formats and every error type for Speech-to-Text, Batch, Text-to-Speech and Voice Cloning, and how to retry safely.

This page lists the errors returned by the Gnani Speech APIs: Speech-to-Text (REST, Realtime and Batch), Text-to-Speech and Voice Cloning. The Agent Builder Platform API has its own codes; see the [Platform API error reference](https://docs.gnani.ai/Platform/Error_Reference.md).

## How errors look

Speech-to-Text (REST) errors use this envelope:

```json theme={null}
{"success": false, "error": {"type": "INVALID_CONTEXT", "message": "…"}}
```

The HTTP status is the reliable signal; branch on `error.type`. These responses use a different shape: validation errors such as a missing `language_code` or `audio_file` (`422` with `{"detail": [...]}`), the `504` on Prisma v3.0, [authentication and rate-limit errors](https://docs.gnani.ai/api/introduction/errors.md#authentication-and-rate-limits), Batch errors, [Text-to-Speech and Voice Cloning errors](https://docs.gnani.ai/api/introduction/errors.md#text-to-speech) and streaming `error` messages.

## Authentication and rate limits

Authentication and rate-limit errors do not use the `success` / `error` envelope. They look like this:

```json theme={null}
{"detail": {"error_code": "RATE_LIMITED", "message": "Only 1 active request is allowed at a time. Wait for your current request to finish before sending another.", "status_code": 429}}
```

| HTTP | `detail.error_code` | Typical cause |
| - | - | - |
| `401` | `MISSING_API_KEY` | The `X-API-Key-ID` header is missing or empty. |
| `401` | `INVALID_API_KEY` | The key is not valid (`"message": "Unauthorized"`). |
| `402` | not verified | Insufficient credit |
| `403` | `SCOPE_NOT_ALLOWED` | The key lacks the scope for this service (for example `Service 'STT' not in allowed scopes`). |
| `429` | `RATE_LIMITED` | Too many requests for your account. For example, an account limited to one active request at a time returns `429` while a request is still running. The response has no `Retry-After` header: wait a moment, then retry with backoff. |

The same shapes are returned by REST, Batch, Text-to-Speech, Voice Cloning and the Realtime handshake (as an HTTP response before the WebSocket opens).

## Speech-to-Text

### Prisma v3.0

| HTTP | `error.type` | When | Example message |
| - | - | - | - |
| 422 | none (body is `{"detail": [...]}`, not the envelope) | `language_code` missing or empty (not for `format=transliterate`, where it is optional) | `{"detail":[{"type":"missing","loc":["body","language_code"],"msg":"Field required","input":null}]}` |
| 422 | none (body is `{"detail": [...]}`) | `audio_file` is missing | `{"detail":[{"type":"missing","loc":["body","audio_file"],"msg":"Field required","input":null}]}` |
| 400 | `INVALID_LANGUAGE_CODE` | A code the service does not recognise (for example `xx-XX`, `hi` or lowercase `hi-in`), or more than 4 languages | `Unsupported languages: xx-XX. Supported languages: as-IN, bn-IN, en-IN, …` or `At most 4 languages are allowed, got 5: hi-IN, en-IN, ta-IN, te-IN, kn-IN.` |
| 400 | `MODEL_UNSUPPORTED_LANGUAGE` | A locale the model does not cover (for example `as-IN`) | `prisma-v3.0 does not support languages: as-IN. Supported languages for this model: bn-IN, en-IN, …` |
| 400 | `INVALID_MODEL` | `model` is not a known model name | `Invalid model 'foo'. Supported models: prisma-v2.5, prisma-v3.0` |
| 400 | `INVALID_FORMAT` | `format` is not `verbatim`, `transcribe`, `codemix` or `transliterate` (or `codemix` or `transliterate` on another model) | `Invalid format. Supported values are: verbatim, transcribe, codemix, transliterate, or omit format.` |
| 400 | `INVALID_CONTEXT` | Out-of-range value, `<\|` / `\|>` in a value, or too many keyterms or speaker names | `topic must be at most 1600 characters (got 1601)` |
| 400 | `EMPTY_AUDIO` | Zero-byte upload | `Empty audio file received` |
| 400 | `UNSUPPORTED_AUDIO_FORMAT` | File-name extension not supported | `Unsupported audio format. Supported formats: …` |
| 400 | `AUDIO_CONVERSION_ERROR` | The file could not be decoded | `Failed to convert audio format: …` |
| 400 | `MAX_AUDIO_DURATION_EXCEEDED` | Audio longer than the limit | `Audio duration exceeds maximum allowed duration of 30 seconds` |
| 500 | `TRANSCRIPTION_FAILED` | Transcription failed | `Speech recognition service failed to transcribe audio. Please try again.` |
| 500 | `INTERNAL_SERVER_ERROR` | Unexpected failure | `Internal server error occurred. Please try again later.` |
| 504 | `UPSTREAM_TIMEOUT` (field `code`) | Transcription did not finish in time | See the body below |

The `504` body is not the envelope:

```json theme={null}
{
  "error": "Gateway Timeout",
  "code": "UPSTREAM_TIMEOUT",
  "message": "The speech-to-text model failed to respond within the allocated 5000ms limit."
}
```

The `504` bounds the transcription step only, so a request can take longer end to end and still succeed.

### Prisma v2.5

Prisma v2.5 returns the same `error.type` values as Prisma v3.0 where they apply (see the Prisma v3.0 table for the audio errors `EMPTY_AUDIO`, `UNSUPPORTED_AUDIO_FORMAT`, `AUDIO_CONVERSION_ERROR` and `MAX_AUDIO_DURATION_EXCEEDED`, and for `INTERNAL_SERVER_ERROR`). These are the ones specific to v2.5:

| HTTP | `error.type` | When | Example message |
| - | - | - | - |
| 400 | `INVALID_FORMAT` | `format` is not `verbatim` or `transcribe` | `Invalid format. Supported values are: verbatim, transcribe, or omit format.` |
| 400 | `INVALID_LANGUAGE_CODE` | An unsupported code, or more than one language | `Unsupported languages: xx-XX. Supported languages: …` |
| 400 | `INVALID_MODEL` | `model` is not a known model name (`prisma-v2.5` is accepted, and so is leaving `model` out) | `Invalid model 'foo'. Supported models: prisma-v2.5, prisma-v3.0` |
| 422 | none (body is `{"detail": [...]}`) | `language_code` or `audio_file` is missing, or `bias_score` is not a number | `{"detail":[{"type":"missing","loc":["body","language_code"],"msg":"Field required","input":null}]}` |
| 500 | `INTERNAL_SERVER_ERROR` | For example, `substitution_map` is not valid JSON | `Internal server error occurred. Please try again later.` |

Invalid `bias_list` input, or a numeric `bias_score` that is not an allowed value, is skipped and the request succeeds.

### Streaming (Realtime)

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

### Batch

Batch errors use `error` and `message` fields (and the authentication shape above for `401`). Each endpoint returns only the errors that apply to it. A `job_id` that is not a valid UUID returns `422` with a `{"detail": [...]}` body. A `status` filter that is not a known status, on the list and files endpoints, is ignored and returns an empty list.

**Create Job**

**401 Missing API key**

```json theme={null}
{
  "detail": {
    "error_code": "MISSING_API_KEY",
    "message": "Missing API key",
    "status_code": 401
  }
}
```

**400 Unsupported language**

```json theme={null}
{
  "error": "UNSUPPORTED_LANGUAGE",
  "message": "Value error, This service does not support language_code 'xx-XX'. Supported languages: bn-IN, en-IN, gu-IN, hi-IN, kn-IN, ml-IN, mr-IN, pa-IN, ta-IN, te-IN"
}
```

**400 Invalid config (Prisma v3.0 options)**

```json theme={null}
{
  "error": "INVALID_CONFIG",
  "message": "Invalid config: … Value error, send one of: keyterms, topic, topic + keyterms, or speaker_names (got keyterms, speaker_names) …"
}
```

The text after `Value error,` says what is wrong:

| Cause | Reason |
| - | - |
| `format`, `keyterms`, `topic` or `speaker_names` sent with another model | `format, keyterms are only supported with model 'prisma-v3.0'` (lists the fields you sent) |
| 5 or more codes in `language_code` | `prisma-v3.0 accepts at most 4 candidate languages (got 5); use "auto" to let the model identify the language among all supported languages` |
| Unsupported combination of context fields | `send one of: keyterms, topic, topic + keyterms, or speaker_names (got keyterms, speaker_names)` |
| `format` is not one of the three styles | `input should be 'verbatim', 'transcribe' or 'codemix'` |
| Too many keyterms | `keyterms accepts at most 200 items (got 201)` |
| `topic` length | `topic must be 30-1600 characters (got 12)` |
| Too many names | `speaker_names accepts at most 4 names (got 5)` |
| A name that spans several lines | `speaker_names must each be a single line` |
| `<\|` or `\|>` in `keyterms`, `topic` or `speaker_names` | `keyterms must not contain the tag marker '<\|' or '\|>'` |

An unsupported language code, or `auto` mixed with other codes, is rejected the same way on every model.

Other `400` errors on this endpoint:

| `error` | When | Example `message` |
| - | - | - |
| `UNSUPPORTED_LANGUAGE` | `language_code` is missing | `Field required` |
| `INVALID_CONFIG` | The `config` part is missing | `Invalid config: …` (the message names the missing part) |
| `INVALID_CONFIG` | A file has an extension Batch does not accept | `File 'a.xyz' has unsupported format. Supported: ['.aac', '.amr', '.flac', '.m4a', '.mp3', '.mp4', '.ogg', '.opus', '.wav', '.webm']` |
| `NO_FILES_PROVIDED` | The upload has no files | `At least one file must be provided` |
| `FILE_TOO_LARGE` | A file is over 10 MB (use a presigned upload for larger files) | `File 'a.wav' is 11.2 MB — exceeds the 10 MB limit.` |

A `config` part that is not valid JSON currently returns `500 Internal Server Error`. Send valid JSON.

**Start Job**

**409 Already started / finished**

```json theme={null}
{
  "error": "JOB_ALREADY_STARTED",
  "message": "Job cannot be restarted from state 'FAILED'"
}
```

**404 Job not found**

```json theme={null}
{
  "error": "JOB_NOT_FOUND",
  "message": "Job 01900000-0000-7000-8000-000000000000 not found"
}
```

**409 Cancelled before starting**

```json theme={null}
{
  "error": "JOB_CANCELLED",
  "message": "Job was cancelled before starting"
}
```

**Get Job Status**

**404 Job not found**

```json theme={null}
{
  "error": "JOB_NOT_FOUND",
  "message": "Job 01900000-0000-7000-8000-000000000000 not found"
}
```

**Cancel Job**

**409 Already cancelled**

```json theme={null}
{
  "error": "JOB_CANCELLED",
  "message": "Job is already cancelled"
}
```

**404 Job not found**

```json theme={null}
{
  "error": "JOB_NOT_FOUND",
  "message": "Job 01900000-0000-7000-8000-000000000000 not found"
}
```

**409 Already finished**

```json theme={null}
{
  "error": "JOB_ALREADY_COMPLETED",
  "message": "Job has already finished with status 'COMPLETED'"
}
```

**File errors**

A file that ends in `FAILED` can carry an `error_code`.

| `error_code` | Meaning |
| - | - |
| `INVALID_RECOGNITION_OPTIONS` | **Prisma v3.0.** The speech service refused the job's `format`, `keyterms`, `topic` or `speaker_names` (for example, because context is switched off in that deployment). Every segment would be refused the same way, so the file fails at once. |
| `UNSUPPORTED_LANGUAGE` | The model refused a language. This also covers its `MODEL_UNSUPPORTED_LANGUAGE`. |

All other file errors are unchanged.

## Text-to-Speech

REST and SSE requests return a flat error body:

Text-to-Speech and Voice Cloning (REST and SSE) return errors in a flat body, not the `error.type` envelope used by Speech-to-Text:

```json theme={null}
{"success": false, "message": "Invalid request: Field required at body -> text", "status_code": 400}
```

| HTTP | When | Example `message` |
| - | - | - |
| `400` | A parameter is missing or invalid: `text`, `voice`, `model`, `speed` (the allowed range depends on the model), or a value in `audio_config` | `Invalid request: Value error, sample_rate must be one of [8000, 16000, 22050, 24000, 44100, 48000], got 12345 at body -> audio_config -> sample_rate` |
| `400` | Unknown `model`, or `vachana-vc-v1` without a `speaker_embedding` | `Model 'bogus' is not supported. The supported models are "timbre-v2.5", "timbre-v3.0". …` |
| `400` | Empty audio sent to the embeddings endpoint | `Audio file is empty` |
| `500` | Unexpected failure, including text that is too long and an invalid `speaker_embedding` or reference audio | `We are facing technical difficulties. Please try again later.` |

Authentication and rate-limit errors use the [shape shown below](https://docs.gnani.ai/api/introduction/errors.md#authentication-and-rate-limits). Some validation failures on the embeddings endpoint can also return `422` with a `{"detail": [...]}` body.

Streaming errors:

**Text-to-Speech** (WebSocket `error` message, and the `error` event on SSE) uses `type` and `message`:

```json theme={null}
{ "type": "error", "message": "Invalid text or audio configuration." }
```

The connection remains open after recoverable errors.

**Voice Cloning** (WebSocket) adds an `error` code:

```json theme={null}
{
  "type": "error",
  "error": "SYNTHESIS_FAILED",
  "message": "Human-readable error description"
}
```

## Voice Cloning

Voice Cloning (inference, SSE and embeddings) returns the same flat error body as Text-to-Speech (see above).

## Retrying

Transcription has no side effects, so retrying is safe. Retry connection errors and `429` / `500` / `503` / `504` with exponential backoff (for example 0.5 s, 1 s, 2 s; three attempts). For `429`, wait a moment before retrying (the response has no `Retry-After` header today, but honour it if one appears). Do not retry other `4xx` errors; they fail the same way. A `TRANSCRIPTION_FAILED` error means the request was already retried once internally.

```python theme={null}
import os
import time
import requests

URL = "https://api.vachana.ai/stt/v3"
HEADERS = {"X-API-Key-ID": "<API_KEY>"}
RETRYABLE = {429, 500, 503, 504}

def transcribe_with_retry(path, data, attempts=3):
    delay = 0.5
    for attempt in range(1, attempts + 1):
        wait = delay
        try:
            with open(path, "rb") as f:
                r = requests.post(
                    URL,
                    headers=HEADERS,
                    files={"audio_file": (os.path.basename(path), f)},
                    data=data,
                    timeout=60,
                )
            if r.status_code not in RETRYABLE:
                return r                      # success, or a 4xx that retrying will not fix
            retry_after = r.headers.get("Retry-After", "")
            if r.status_code == 429 and retry_after.isdigit():
                wait = max(wait, int(retry_after))
        except (requests.ConnectionError, requests.Timeout):
            pass
        if attempt < attempts:
            time.sleep(wait)
            delay *= 2
    raise RuntimeError(f"still failing after {attempts} attempts")

r = transcribe_with_retry("clip.wav", {"model": "prisma-v3.0", "language_code": "indic-auto"})
body = r.json()
if body.get("success"):
    print(body["transcript"])
else:
    err = body.get("error") or body.get("detail") or {}   # 401/429 use "detail"
    if isinstance(err, dict):
        print(r.status_code, err.get("type") or err.get("error_code"), err.get("message"))
    else:
        print(r.status_code, err)                        # 422 validation errors are a list
```

Try an invalid request to see the envelope:

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form language_code=hi-IN \
  --form format=unknown
```

## Reporting a problem

Send the `request_id` from the response (or the one you set in `X-API-Request-ID`) to support.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.