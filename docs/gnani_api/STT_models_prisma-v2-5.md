> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Prisma v2.5

> The default speech-to-text model for Indian languages. You choose the language, and it returns the words as text, with optional number formatting, find-and-replace and word boosting.

## Overview

**Prisma v2.5** is Gnani's default speech-to-text model. You send it audio of someone speaking, tell it which language to expect, and it returns the words as text.

What it gives you:

* **Ten languages.** Nine Indian languages and English, each requested by its language code. You send one language code with every request (see [Languages](#languages)).
* **Number formatting.** `format=transcribe` writes numbers, currency, dates, times and phone numbers the way a reader expects, for example `₹5,000` instead of "five thousand rupees" (see [Output styles](#output-styles)).
* **Word boosting.** `bias_list` and `bias_score` nudge the model towards brand names and other words it tends to mishear (see [Word boosting](#word-boosting)).
* **Find-and-replace.** Rewrite words in the final transcript, for example `ok` to `acknowledged` (see [Find-and-replace](#find-and-replace)).

> [!NOTE]
>
> **Prisma v2.5 is the default.** If a request does not choose a model, the API uses Prisma v2.5, so existing integrations keep working unchanged. For automatic language detection (`indic-auto`), lists of one to four languages, the `codemix` and `transliterate` output styles and context hints, see [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md). For all models, see [Models](https://docs.gnani.ai/api/STT/models/overview.md).

## Quick facts

| | |
| - | - |
| **Model name** | `prisma-v2.5`. This is the value the API reports in responses and the value you set in a Batch job's `config.model`. |
| **How you select it** | Leave out `model` (REST and Realtime). On Batch, `config.model` is required, so send `prisma-v2.5`. See [Selecting Prisma v2.5](#selecting-prisma-v2-5). |
| **Languages** | Nine Indian languages and English. You always send one language code. See [Languages](#languages). |
| **Ways to write the text** | `verbatim` (default) and `transcribe`. See [Output styles](#output-styles). |
| **Audio you can send** | For short files over REST: WAV, MP3, OGG, FLAC, AAC or M4A. For live audio over WebSocket: raw PCM frames (signed 16-bit little-endian). For Batch, see [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md#supported-audio-formats). |
| **Longest file over REST** | 30 seconds per request. Use the Batch API for longer recordings (see [Limits](https://docs.gnani.ai/api/STT/limits.md)). |

## Selecting Prisma v2.5

Prisma v2.5 runs unless you ask for another model. On REST, leave `model` out or pass `prisma-v2.5`. On Realtime, leave out `model` or pass `prisma-v2.5`. On Batch, set `config.model` to `prisma-v2.5`. See [Where you can use it](#where-you-can-use-it).

The `3` in `/stt/v3` is the URL version, not the model version. How models and URLs relate, and how to select each model, is explained on the [Models](https://docs.gnani.ai/api/STT/models/overview.md) page.

To use Prisma v3.0 instead, add `model=prisma-v3.0` to your request. To go back, remove it.

## Where you can use it

Gnani offers several ways to send audio. Prisma v2.5 works with all of them.

| Use this | When | What it is | How to select Prisma v2.5 |
| - | - | - | - |
| [**REST: `POST /stt/v3`**](https://docs.gnani.ai/api/STT/speech-to-text) | You have a short recording (up to 30 seconds) and want the transcript straight back. | You upload the audio file in one HTTP request and the transcript comes back in the response. | Leave out `model`. |
| [**Realtime: `WS /stt/v3/stream`**](https://docs.gnani.ai/api/STT/stt-websocket) | The audio is live, such as a phone call or a microphone, and you want text while the conversation is happening. | You open a WebSocket connection and send audio continuously. Transcripts arrive as the speaker finishes each sentence. | Leave out the `model` header, or send `model: prisma-v2.5`. |
| [**Batch Jobs API**](https://docs.gnani.ai/api/STTBatch/Introduction.md) | You have many files, or recordings longer than 30 seconds, and can wait for the results. | You create a job that points to your audio files. The files are processed in the background and you collect the results when the job is done. | Set `model` to `prisma-v2.5` inside the job's `config`. `model` is always required on Batch. |

## Try it

This request sends one audio file and asks for Hindi. Replace `<API_KEY>` with your Gnani API key and `clip.wav` with your own file (up to 30 seconds).

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form language_code=hi-IN
```

```python theme={null}
import requests

API_KEY = "<API_KEY>"

with open("clip.wav", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": API_KEY},
        files={"audio_file": ("clip.wav", f, "audio/wav")},
        data={"language_code": "hi-IN"},
        timeout=60,
    )

body = r.json()
if body.get("success"):
    print(body["transcript"])
else:
    print(body["error"]["type"], body["error"]["message"])
```

A successful response looks like this:

```json theme={null}
{
  "success": true,
  "request_id": "req_abc123",
  "transcript": "नमस्ते, आप कैसे हैं?",
  "model": "prisma-v2.5",
  "processing_time": 0.14,
  "end_to_end_latency": 0.17,
  "output": {
    "literal": "नमस्ते, आप कैसे हैं?"
  }
}
```

| Field | Meaning |
| - | - |
| `success` | `true` when the audio was transcribed. When it is `false`, the response has an `error` object instead (see [Error Reference](https://docs.gnani.ai/api/introduction/errors.md#prisma-v2-5)). |
| `request_id` | Your `X-API-Request-ID`, or a generated id. Quote it if you contact Gnani support about a specific request. |
| `transcript` | The text of what was said. An empty string when there is no speech. |
| `model` | `prisma-v2.5`. |
| `processing_time`, `end_to_end_latency` | Seconds spent on the request, and seconds since it arrived (this includes your upload time). |
| `output.literal` | The transcript before inverse text normalization (ITN) is applied. It is the same as `transcript` when ITN changes nothing. |
| `truncated` | Only when it happens: `true` when the model hit its token limit and the transcript was cut short. Retry with shorter audio. |

The example above shows the main fields. The full field list for the response is on [REST transcription](https://docs.gnani.ai/api/STT/speech-to-text.md#response).

## Languages

Use these codes in `language_code`. Each code is a language followed by a region, for example `hi-IN` for Hindi as spoken in India.

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

Prisma v2.5 does not identify the language for you. You send the language you expect, and the audio is transcribed in it. On REST, automatic detection (`indic-auto`) is a [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md#language-detection) feature. On Realtime, `indic-auto` is also accepted without a `model` header, but only Prisma v3.0 returns `detected_language_code`.

How you give the language depends on how you send the audio:

| Access method | How to choose the language |
| - | - |
| **REST** | Send one `language_code`. |
| **Realtime** | Send one `language_code` when you connect (or `indic-auto`). Streaming is single-language: one language per session. |
| **Batch** | Send one code in `config.language_code`, or up to **three** codes separated by commas. With several codes, each file is identified as one of those languages and transcribed in it. The first code is the fallback. See [Language identification](https://docs.gnani.ai/api/STTBatch/Introduction.md#language-identification). |

## Output styles

The same audio can be written two ways. Set it with `format` (REST and Realtime).

| `format` | What you get | Numbers and symbols | Use when |
| - | - | - | - |
| `verbatim` (default) | the raw spoken-form text | spelled out as words | you want exactly what was said, or you use word boosting |
| `transcribe` | spoken-form text run through Inverse Text Normalization (ITN) | digits, currency signs, dates, times and phone numbers in their written form | you want `₹5,000` or `9876543210` |

* **`verbatim` is always the default.** If you leave out `format`, you get `verbatim`, whatever the language.
* **ITN currently works for `hi-IN` and `en-IN` only.**
* **Not available on Batch.** `format` is a Prisma v3.0 option on Batch, and ITN is not supported there. A Batch job on Prisma v2.5 that sends `format` returns `400 INVALID_CONFIG`.
* **The other two styles belong to Prisma v3.0.** `codemix` and `transliterate` are not available on Prisma v2.5.

### The same clip in both styles

```bash theme={null}
for STYLE in verbatim transcribe; do
  echo "== $STYLE"
  curl --silent --location "https://api.vachana.ai/stt/v3" \
    --header "X-API-Key-ID: <API_KEY>" \
    --form audio_file=@clip.wav \
    --form language_code=hi-IN \
    --form format=$STYLE
  echo
done
```

```python theme={null}
import requests

for style in ("verbatim", "transcribe"):
    with open("clip.wav", "rb") as f:
        r = requests.post(
            "https://api.vachana.ai/stt/v3",
            headers={"X-API-Key-ID": "<API_KEY>"},
            files={"audio_file": ("clip.wav", f, "audio/wav")},
            data={"language_code": "hi-IN", "format": style},
            timeout=60,
        )
    print(style, "->", r.json()["transcript"])
```

*Example output for a clip of someone saying "five thousand rupees" in Hindi (your text will differ):*

| `format` | Transcript |
| - | - |
| `verbatim` | `पाँच हज़ार रुपये` |
| `transcribe` | `₹5,000` |

### Digits in the native script

With `format=transcribe`, set `itn_native_numerals=true` to write digits in the native script of the language instead of Western digits. It has no effect with `verbatim`.

| `itn_native_numerals` | Hindi, "five thousand rupees" |
| - | - |
| `false` (default) | `₹5,000` |
| `true` | `₹५,०००` |

The parameter is called `itn_native_numerals` on both REST and Realtime. (On Prisma v3.0 it has no effect.)

### Output style when streaming

```python theme={null}
headers = {
    "x-api-key-id": "<API_KEY>",
    "language_code": "hi-IN",
    "format": "transcribe",           # verbatim | transcribe
    "itn_native_numerals": "true",    # optional
}
# connect as shown on the Realtime streaming page
```

On Prisma v2.5 ITN runs on every transcript segment, straight after recognition. When number formatting runs, the `transcript` message also carries `output.literal` with the text before formatting (equal to `text` when formatting changed nothing). For what ITN converts and what it leaves alone, see the [ITN reference](https://docs.gnani.ai/api/STT/stt-websocket.md#inverse-text-normalization-itn).

## Word boosting

Word boosting nudges the model towards specific words, so they are more likely to be written correctly. Use it for brand names, product names and other terms the model tends to mishear. It changes recognition itself. It is not a find-and-replace.

Send both fields together:

| Field | What it is | Allowed |
| - | - | - |
| `bias_list` | the words to favour | up to 100 words, as a JSON array (`["EMI","Prisma"]`) or comma-separated (`EMI,Prisma`) |
| `bias_score` | how strongly to favour them | one of `0.0`, `0.5`, `1.0`, `1.5`, `2.0` |

| `bias_score` | Effect |
| - | - |
| `0.0` | Off (same as leaving it out) |
| `0.5` | Light nudge |
| `1.0` | Typical starting point |
| `1.5` | Stronger |
| `2.0` | Maximum |

Start at `1.0` and raise it only if a word is still missed. A stronger score can make the model favour a listed word where it was not spoken.

* **Each entry is one word, letters only.** Latin or Indian-script letters. No spaces, digits, punctuation or symbols, so `"loan number"` and `HDFC2` are not allowed.
* **Casing does not matter.**
* **Use `format=verbatim`.** Boost words are spoken-form words, so digit strings and formatted numbers will not work.
* **Bad input is skipped, not rejected.** On REST and when streaming, if any entry breaks the rules or `bias_score` is not an allowed value, the whole list is ignored and the audio is transcribed without boosting. You still get a normal response. The exception on REST is a `bias_score` that is not a number at all (for example `abc`), which is rejected with `422`. On Batch, an invalid list or score is rejected when the job is created (`400 INVALID_CONFIG`).
* **Works on REST, Realtime and Batch.** Streaming uses the headers `bias_list` and `bias_score`, and you can change them mid-session with `update_settings`. See [Word boosting on Realtime](https://docs.gnani.ai/api/STT/stt-websocket.md#word-boosting) and [Word boosting on Batch](https://docs.gnani.ai/api/STTBatch/Introduction.md#word-boosting).

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form language_code=hi-IN \
  --form format=verbatim \
  --form 'bias_list=["Prisma","EMI"]' \
  --form bias_score=1.0
```

```python theme={null}
import json
import requests

with open("clip.wav", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": "<API_KEY>"},
        files={"audio_file": ("clip.wav", f, "audio/wav")},
        data={
            "language_code": "hi-IN",
            "format": "verbatim",
            "bias_list": json.dumps(["Prisma", "EMI"]),
            "bias_score": "1.0",
        },
        timeout=60,
    )
print(r.json()["transcript"])
```

> [!NOTE]
>
> Prisma v3.0 replaces this with `keyterms` (up to 200 words or short phrases), `topic`, `previous_text` and `speaker_names`. See [Context](https://docs.gnani.ai/api/STT/models/prisma-v3.md#context).

## Find-and-replace

After recognition, and after number formatting if you use it, the API can rewrite words in the final transcript. Use it to standardise terms, for example `rs` to `INR`.

| Field | What it is |
| - | - |
| `enable_substitution` | `true` to turn find-and-replace on. The default is `false`. |
| `substitution_map` | a JSON list of rules. At most 10 rules. |

Each rule has `patterns`, the strings to find, and `replacement`, the text to put in their place. Matching ignores case and respects Unicode word boundaries, so `ok` matches `OK` but not `okay`. Rules are applied in a single pass, and longer phrases win over shorter ones.

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form language_code=en-IN \
  --form enable_substitution=true \
  --form 'substitution_map=[{"patterns":["okay","ok"],"replacement":"acknowledged"},{"patterns":["rupees","rs"],"replacement":"INR"}]'
```

It works on REST and when streaming (`enable_substitution` and `substitution_map`, which you can change mid-session). It is not supported on Batch. See [Find-and-replace on REST](https://docs.gnani.ai/api/STT/speech-to-text.md#find-and-replace-substitution) and [on Realtime](https://docs.gnani.ai/api/STT/stt-websocket.md#find-and-replace-substitution) for the full rules.

## Batch jobs

A Batch job on Prisma v2.5 sets `config.model` to `prisma-v2.5`. The language is identified per file, from up to three codes, and diarization, denoising and webhooks are the same as for every model.

| In a job's `config` | On Prisma v2.5 |
| - | - |
| `model` | `prisma-v2.5`, always required |
| `language_code` | one code, or up to three comma-separated codes. More than three returns `400 UNSUPPORTED_LANGUAGE`. |
| `bias_list`, `bias_score` | supported (see [Word boosting](#word-boosting)) |
| `with_diarization`, `num_speakers`, `is_multi_channel`, `with_denoise` | supported |
| `format`, `keyterms`, `topic`, `speaker_names` | **`400 INVALID_CONFIG`.** These are Prisma v3.0 options. They are refused, not ignored. |

Number formatting (ITN), `previous_text` and find-and-replace are not available on Batch. The full reference is [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md).

## What Prisma v2.5 does not do

These are capabilities of [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md). They are not available on Prisma v2.5:

* **Automatic language detection** (`indic-auto`) on REST, and lists of languages on REST and Realtime. You choose one language. (Realtime also accepts `indic-auto` without a `model` header.) (Batch accepts up to three codes.)
* **`detected_language_code`** in the response.
* **The `codemix` and `transliterate` output styles.**
* **Context hints:** `keyterms`, `topic`, `previous_text` and `speaker_names`. Prisma v2.5 has word boosting instead.

Some restrictions depend on how you send the audio:

* **REST** accepts clips of up to 30 seconds. Use the [Batch Jobs API](https://docs.gnani.ai/api/STTBatch/Introduction.md) for longer recordings.
* **Realtime streaming** is single-language: one `language_code` per session.
* **ITN** works for `hi-IN` and `en-IN` only, and is not available on Batch.

## Limits

| What | Limit |
| - | - |
| Audio length per request (REST) | 30 seconds |
| Audio formats (REST) | WAV, MP3, OGG, FLAC, AAC, M4A |
| `bias_list` | Up to 100 single words |
| `substitution_map` | Up to 10 rules; patterns up to 200 characters |
| Streaming session length | 15 minutes |
| Concurrent streaming sessions | A per-organisation cap applies. A rejected connection receives an `error` message that names the limit. |
| Batch | Up to 4 hours per file, 100 files per upload job, 10 MB per uploaded file. See [Batch limits](https://docs.gnani.ai/api/STTBatch/Introduction.md#limits). |

Request rates and the full table, including Prisma v3.0, are on [Limits](https://docs.gnani.ai/api/STT/limits.md).

## How it differs from Prisma v3.0

The differences are listed in one table on the Prisma v3.0 page: [How it differs from Prisma v2.5](https://docs.gnani.ai/api/STT/models/prisma-v3.md#how-it-differs-from-prisma-v2-5). Check it before you switch, and send a few representative recordings through both models using the same `format`.

## Next steps

* [Models](https://docs.gnani.ai/api/STT/models/overview.md): all Speech-to-Text models and how to choose between them.
* [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md): the newer multilingual model.
* [Speech-to-Text overview](https://docs.gnani.ai/api/STT/overview.md): what works on REST, Realtime and Batch.
* Reference: [REST](https://docs.gnani.ai/api/STT/speech-to-text.md), [Realtime](https://docs.gnani.ai/api/STT/stt-websocket.md) and [Batch](https://docs.gnani.ai/api/STTBatch/Introduction.md).
* [Error Reference](https://docs.gnani.ai/api/introduction/errors.md#prisma-v2-5) and [Limits](https://docs.gnani.ai/api/STT/limits.md).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.