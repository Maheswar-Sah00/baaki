> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Prisma v3.0

> A speech-to-text model for Indian languages that can work out which language is being spoken, handle speech that mixes languages, and use hints such as names and topics to improve accuracy.

## Overview

**Prisma v3.0** is Gnani's multilingual speech-to-text model. You send it audio of someone speaking and it returns the words as text.

What sets it apart from [Prisma v2.5](https://docs.gnani.ai/api/STT/models/prisma-v2-5.md), the model most existing integrations use today:

* **One model for ten languages.** Nine Indian languages and English are covered by a single model. You do not need a separate model or a separate request per language.
* **It can identify the language for you.** If you do not know which language a caller will speak, you can ask the model to work it out. The response then tells you which language it heard (see [Language detection](#language-detection)).
* **It handles mixed-language speech.** People often switch between languages mid-sentence, for example Hindi with English words. You choose how those words are written (see [Output styles](#output-styles)).
* **It accepts hints.** You can pass names, brand terms, the topic of the conversation or the previous part of a recording to help the model get difficult words right (see [Context](#context)).
* **You always get one transcript back.** The response contains a single transcript, not one per language.

> [!NOTE]
>
> **Prisma v3.0 is opt-in.** If a request does not ask for it, the API uses Prisma v2.5 as before. Nothing changes for existing integrations until you add `model=prisma-v3.0` to your requests. For all models, see [Models](https://docs.gnani.ai/api/STT/models/overview.md).

## Quick facts

| | |
| - | - |
| **Model name** | `prisma-v3.0`. You send this value to select the model, and the API returns it in the `model` field of the response. |
| **How you select it** | Add `model=prisma-v3.0` to your request. The exact place depends on the API you use (see [Selecting Prisma v3.0](#selecting-prisma-v3-0) and [Where you can use it](#where-you-can-use-it) below). |
| **Languages** | Nine Indian languages and English, plus `indic-auto`, which means "let the model identify the language". See [Languages](#languages). |
| **Ways to write the text** | `verbatim`, `transcribe`, `codemix` and `transliterate`. The first three control how numbers, symbols and English words are written. `transliterate` writes the whole transcript in Latin letters. See [Output styles](#output-styles). |
| **Audio you can send** | For short files over REST: WAV, MP3, OGG, FLAC, AAC or M4A. For live audio over WebSocket: raw 16-bit PCM (uncompressed audio) from a single channel. |
| **Longest file over REST** | 30 seconds per request. Use the Batch API for longer recordings (see [Limits](https://docs.gnani.ai/api/STT/limits.md)). |

## Selecting Prisma v3.0

Send `model=prisma-v3.0` to run Prisma v3.0. Where you put it depends on the API (see [Where you can use it](#where-you-can-use-it)). Leave it out on REST or Realtime to run Prisma v2.5, the default.

The `3` in `/stt/v3` is the URL version, not the model version. How models and URLs relate, and how to select each model, is explained on the [Models](https://docs.gnani.ai/api/STT/models/overview.md) page.

## Where you can use it

Gnani offers several ways to send audio. Prisma v3.0 works with all of them. Pick the one that matches how your audio is produced.

| Use this | When | What it is | How to select Prisma v3.0 |
| - | - | - | - |
| [**REST: `POST /stt/v3`**](https://docs.gnani.ai/api/STT/speech-to-text) | You have a short recording (up to 30 seconds) and want the transcript straight back. | You upload the audio file in one HTTP request and the transcript comes back in the response. | Add the form field `model=prisma-v3.0`. |
| [**Realtime: `WS /stt/v3/stream`**](https://docs.gnani.ai/api/STT/stt-websocket) | The audio is live, such as a phone call or a microphone, and you want text while the conversation is happening. | You open a WebSocket connection (a connection that stays open) and send audio continuously. Transcripts arrive as the speaker finishes each sentence. | Add the header `x-model: prisma-v3.0` when you connect. |
| [**Batch Jobs API**](https://docs.gnani.ai/api/STTBatch/Introduction.md) | You have many files, or recordings longer than 30 seconds, and can wait for the results. | You create a job that points to your audio files. The files are processed in the background and you collect the results when the job is done. | Set `model` to `prisma-v3.0` inside the job's `config`. `model` is always required on Batch. |

## Try it

This request sends one audio file and asks the model to identify the language automatically. Replace `<API_KEY>` with your Gnani API key and `clip.wav` with your own file (up to 30 seconds).

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form language_code=indic-auto
```

```python theme={null}
import requests

API_KEY = "<API_KEY>"

with open("clip.wav", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": API_KEY},
        files={"audio_file": ("clip.wav", f, "audio/wav")},
        data={"model": "prisma-v3.0", "language_code": "indic-auto"},
        timeout=60,
    )

body = r.json()
if body.get("success"):
    print(body["transcript"], body.get("detected_language_code"))
else:
    print(body["error"]["type"], body["error"]["message"])
```

A successful response looks like this:

```json theme={null}
{
  "success": true,
  "request_id": "5c1f0a52-6d62-4e0b-9a38-2f2b8a8f7a10",
  "transcript": "வணக்கம் எப்படி இருக்கீங்க",
  "model": "prisma-v3.0",
  "detected_language_code": "ta-IN",
  "processing_time": 0.58,
  "end_to_end_latency": 0.66
}
```

| Field | Meaning |
| - | - |
| `success` | `true` when the audio was transcribed. When it is `false`, the response has an `error` object instead (see [Error Reference](https://docs.gnani.ai/api/introduction/errors.md)). |
| `request_id` | A unique ID for this request. Quote it if you contact Gnani support about a specific request. |
| `transcript` | The text of what was said. |
| `model` | The model that handled the request. It is `prisma-v3.0` here. |
| `detected_language_code` | The language of the transcript, judged from the script it is written in. It is returned on every request, including when you fix the language yourself. It is left out when there is nothing to judge, such as an empty transcript. See [Reading `detected_language_code`](#reading-detected_language_code). |
| `processing_time` | How long the model took to transcribe the audio, in seconds. |
| `end_to_end_latency` | The total time the request took, in seconds. |

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

> [!NOTE]
>
> **`indic-auto` (Prisma v3.0 only).** Send `language_code=indic-auto` to let the model identify the language itself. It is not a language: the reply carries the language it heard in `detected_language_code`. See [Language detection](https://docs.gnani.ai/api/STT/models/prisma-v3.md#language-detection).

Languages outside this list, such as Assamese (`as-IN`), are not supported by Prisma v3.0.

You tell the model which languages to expect by sending `indic-auto`, or one to four language codes. They are explained under [Language detection](#language-detection).

## Language detection

Prisma v3.0 always detects the language from the audio. The `transcript` follows the language that is actually spoken, and `detected_language_code` reports it. The tag is worked out from the script of the final transcript (see [Reading `detected_language_code`](#reading-detected_language_code)).

`language_code` tells the model which languages to expect. It doesn't force the output into a language.

| What you send | What the model does | Tag in the reply |
| - | - | - |
| `language_code=indic-auto` | Listens for all 10 supported languages and identifies the one spoken | `detected_language_code` |
| 1–4 languages, e.g. `language_code=hi-IN` or `language_code=hi-IN,en-IN` | Listens for your languages first. If the audio is clearly in another language, the transcript follows that language. | `detected_language_code` |

### Good to know

* **What you send is a hint, not a lock.** Passing `hi-IN` doesn't guarantee a Hindi transcript. If the speaker uses Tamil, you get Tamil, and the tag says `ta-IN`.
* **You can send up to 4 languages.** Order doesn't matter.
* **When to list languages:** if you know the likely languages, list them. It helps most with short clips and with languages that share a script, such as Hindi and Marathi.
* **When to use auto:** use `indic-auto` when you don't know what the caller will speak.
* **Always check `detected_language_code`** to see which language was transcribed.

### Auto-detect the language

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form language_code=indic-auto
```

```python theme={null}
import requests

with open("clip.wav", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": "<API_KEY>"},
        files={"audio_file": ("clip.wav", f, "audio/wav")},
        data={"model": "prisma-v3.0", "language_code": "indic-auto"},
        timeout=60,
    )
print(r.json())
```

The response names the language it heard:

```json theme={null}
{
  "success": true,
  "request_id": "5c1f0a52-6d62-4e0b-9a38-2f2b8a8f7a10",
  "transcript": "मला उद्या मीटिंगला जायचं आहे",
  "model": "prisma-v3.0",
  "detected_language_code": "mr-IN",
  "processing_time": 0.71,
  "end_to_end_latency": 0.8
}
```

### Send one language

Send one code when you expect a single language. The model listens for that language first. If the speaker uses another language, the `transcript` and `detected_language_code` follow it:

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form language_code=hi-IN \
  --form format=transcribe
```

```python theme={null}
import requests

with open("clip.wav", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": "<API_KEY>"},
        files={"audio_file": ("clip.wav", f, "audio/wav")},
        data={"model": "prisma-v3.0", "language_code": "hi-IN", "format": "transcribe"},
        timeout=60,
    )
print(r.json()["transcript"])
```

```json theme={null}
{
  "success": true,
  "request_id": "0b7d6a1e-3c9f-4f0e-8a51-6f4c1d2b9e77",
  "transcript": "मेरा खाता नंबर 12345 है",
  "model": "prisma-v3.0",
  "detected_language_code": "hi-IN",
  "processing_time": 0.55,
  "end_to_end_latency": 0.63
}
```

### Send several languages

Hindi and English are both likely:

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form language_code=hi-IN,en-IN
```

```python theme={null}
import requests

with open("clip.wav", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": "<API_KEY>"},
        files={"audio_file": ("clip.wav", f, "audio/wav")},
        data={"model": "prisma-v3.0", "language_code": "hi-IN,en-IN"},
        timeout=60,
    )
body = r.json()
print(body["transcript"], body["detected_language_code"])   # a string, never a dict
```

### Reading `detected_language_code`

The model transcribes but does not report which language it heard. For every request except `format=transliterate`, the API adds `detected_language_code`, derived from the **script of the final transcript**. The same logic runs whatever you send. Only the languages it starts from differ.

| Request | Languages it starts from | Tag |
| - | - | - |
| `POST /stt/v3`, one or more languages | the languages you sent | yes, when the transcript contains letters |
| `POST /stt/v3`, `indic-auto` | none | yes, when the transcript contains letters |
| Streaming, any `language_code` | as above | on every committed transcript that has text |
| `format=transliterate` (REST or streaming) | not used | no |

* **It describes what the transcript is written in**, not what the model was told. If you send `ta-IN` and the speaker answers in English, the tag is `en-IN`. If you send `hi-IN` and the text comes back in Tamil script, the tag is `ta-IN`.
* The tag reports what was written, even when it is outside the languages you sent.
* Empty transcripts, transcripts of digits or punctuation only, and text in a script the API does not map (for example Urdu or Odia) have no tag.
* **With `format=transliterate` there is no tag.** The text is always in Latin letters, so there is nothing to judge a language from.
* Code-mixed output keeps its native-language tag while native-script letters make up at least 30 % of the letters. A transcript that is mostly English with a short native phrase can be tagged `en-IN`.
* **Hindi vs Marathi:** both use Devanagari, so very short utterances (a greeting, a name, a number) may be tagged `hi-IN`. Sending only the one you expect, `hi-IN` or `mr-IN`, settles it.
* When streaming, the tag is judged per committed utterance, so it can change from one message to the next when the speaker switches language.

**Streaming.** Add `model: prisma-v3.0` and `language_code: indic-auto` (or a list such as `hi-IN,en-IN`) to the connection headers. The full connection example is on the [Realtime page](https://docs.gnani.ai/api/STT/stt-websocket.md#example-python).

```python theme={null}
HEADERS = {
    "x-api-key-id": "<API_KEY>",
    "model": "prisma-v3.0",
    "language_code": "indic-auto",   # or "hi-IN,en-IN", or one language
    "x-sample-rate": "16000",
}
```

Each committed `transcript` message then carries `detected_language_code`.

### Related language errors

A missing `language_code` (`422`, except with `format=transliterate`), `INVALID_LANGUAGE_CODE` and `MODEL_UNSUPPORTED_LANGUAGE` are listed in [Error Reference](https://docs.gnani.ai/api/introduction/errors.md).

## Output styles

The same audio can be written four ways. Set it with `format` (REST and streaming) or `config.format` (Batch). The last column shows where each style is available.

| `format` | English words | Numbers and symbols | Use when | Available on |
| - | - | - | - | - |
| `verbatim` | written in the native script (speech that is entirely English is still written in Latin) | spelled out as words | everything must be in the native script | REST, Realtime, Batch |
| `transcribe` | stay in Latin | digits, symbols, currency signs | you want `12345`, `%`, `₹` | REST, Realtime, Batch |
| `codemix` | stay in Latin | mostly spoken out as words in the native language | English words stay Latin but numbers stay words | REST, Realtime, Batch |
| `transliterate` | the whole transcript is in Latin letters | spelled out as words | you want the speech written in Latin letters (romanised, Hinglish-style) | REST, Realtime |

**What you get when you omit `format`** (REST)

| Situation | Style |
| - | - |
| one language, `hi-IN` or `en-IN` | `transcribe` |
| one language, any other | `verbatim` |
| auto (`indic-auto`) | `verbatim` |

An explicit `format` always wins. When streaming, the style is chosen per session. See [Output style when streaming](#output-style-when-streaming).

> [!WARNING]
>
> A single `hi-IN` or `en-IN` with no `format` returns **digits** on v3.0. On v2.5 the default was `verbatim`. Send `format` explicitly when moving over, to keep your current output.

### Romanised output (`transliterate`)

With `format=transliterate` the model writes Indic speech in Latin letters, for example `तो ठीक है` becomes `to theek hai`. It is available on REST and when streaming. Numbers come out as words.

* **`language_code` is optional.** The model romanises whatever language it hears, so there is nothing to tell it. If you leave it out (or send it empty), the request is treated as `indic-auto`. For every other format it stays required.
* **If you do send a language, it is still checked.** An unsupported locale (such as `as-IN`) is an error. It does not change what the model does.
* **A list of languages is ignored.** One call returns one transcript.
* **The reply has no `detected_language_code`.** The text is always in Latin letters, so there is nothing to judge a language from. If you need to know the language, take it from your own request.
* **`keyterms`, `topic`, `previous_text` and `speaker_names` work as usual.** Write them in Latin letters to match the output.

> [!WARNING]
>
> The romanisation is written by the model, and its accuracy has not been measured. The output is always in Latin letters, but compare it with what you expect on your own audio before relying on it.

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form format=transliterate
```

```python theme={null}
import requests

with open("clip.wav", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": "<API_KEY>"},
        files={"audio_file": ("clip.wav", f, "audio/wav")},
        data={"model": "prisma-v3.0", "format": "transliterate"},   # no language_code needed
        timeout=60,
    )
print(r.json()["transcript"])
```

```json theme={null}
{
  "success": true,
  "request_id": "5c1f0a52-6d62-4e0b-9a38-2f2b8a8f7a10",
  "transcript": "to theek hai",
  "model": "prisma-v3.0",
  "processing_time": 0.58,
  "end_to_end_latency": 0.66
}
```

### The same clip in all four styles

```bash theme={null}
for STYLE in verbatim transcribe codemix transliterate; do
  echo "== $STYLE"
  curl --silent --location "https://api.vachana.ai/stt/v3" \
    --header "X-API-Key-ID: <API_KEY>" \
    --form audio_file=@clip.wav \
    --form model=prisma-v3.0 \
    --form language_code=hi-IN \
    --form format=$STYLE
  echo
done
```

```python theme={null}
import requests

for style in ("verbatim", "transcribe", "codemix", "transliterate"):
    with open("clip.wav", "rb") as f:
        r = requests.post(
            "https://api.vachana.ai/stt/v3",
            headers={"X-API-Key-ID": "<API_KEY>"},
            files={"audio_file": ("clip.wav", f, "audio/wav")},
            data={"model": "prisma-v3.0", "language_code": "hi-IN", "format": style},
            timeout=60,
        )
    print(style, "->", r.json()["transcript"])
```

*Example output for a clip containing a number and an English word (your text will differ):*

| `format` | Transcript |
| - | - |
| `verbatim` | `मेरा अकाउंट नंबर एक दो तीन चार पाँच है` (English words in native script, numbers as words) |
| `transcribe` | `मेरा account नंबर 12345 है` |
| `codemix` | `मेरा account नंबर एक दो तीन चार पाँच है` |
| `transliterate` | `mera account number ek do teen char paanch hai` |

### Output style when streaming

Streaming supports all four styles. The model writes the style you ask for, exactly as it does on REST, so a `transcribe` session returns the same text as REST. There is no separate number-formatting step afterwards.

```python theme={null}
import json

headers = {
    "x-api-key-id": "<API_KEY>",
    "model": "prisma-v3.0",
    "language_code": "hi-IN",
    "format": "transcribe",       # verbatim | transcribe | codemix | transliterate
}
# connect as shown in the [Realtime example](/api/STT/stt-websocket#example-python)
await ws.send(json.dumps({"type": "update_settings", "format": "verbatim"}))   # applies from the next utterance
```

| You send | Style |
| - | - |
| `format: transcribe` | `transcribe` |
| `format: verbatim` | `verbatim` |
| `format: codemix` | `codemix` |
| `format: transliterate` | `transliterate` (Latin letters; `language_code` becomes optional) |
| no `format`, one language, `hi-IN` / `en-IN` | `transcribe` (default) |
| no `format`, any other language, `indic-auto`, or a list of languages | `verbatim` |

* **`itn_native_numerals` has no effect** on `prisma-v3.0`, on REST or when streaming. The model writes numbers itself.
* **`format: transliterate`** works as described in [Romanised output](#romanised-output-transliterate): `language_code` is optional (it defaults to `indic-auto`), a list of languages is ignored, and `detected_language_code` is not sent. You can switch into and out of it with `update_settings`. When you leave it, the session's own language applies again.
* **`output.literal` is not returned** for `prisma-v3.0`, on REST or when streaming. There is no separate step that changes the text, so there is no "before formatting" text.

## Context

Context is extra information sent with the audio — names, brands, what the call is about. There are four kinds. This section describes REST and Realtime. On Batch, `keyterms`, `topic` and `speaker_names` are `config` fields with stricter limits and fewer allowed combinations, and `previous_text` is not available. See [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md#context).

| Field | Streaming | What it is | Allowed size |
| - | - | - | - |
| `keyterms` | same name, as a header | words or short phrases to favour: names, brands, product terms, rare words | up to 200 items |
| `topic` | same name, as a header | a sentence or paragraph about the recording | any non-empty text, up to 1,600 characters (no minimum) |
| `previous_text` | same name, as a header | transcript of the clip just before this one (for recordings cut into pieces) | any non-empty text (no minimum); the last 600 characters are kept |
| `speaker_names` | same name, as a header | names that may be spoken | 1–4 names, one line each |

`bias_list` still works on this model as the older name of `keyterms`. If both are sent, `keyterms` wins. `bias_score` is ignored.

**Combining fields.** You can send any combination of the four fields, from none to all four, for example `keyterms` + `previous_text`, or `topic` + `keyterms` + `speaker_names` + `previous_text`. Each field keeps its own limits from the table above. In Gnani's tests on 60 public clips per combination, every combination that included `keyterms` was more accurate than no context and none was worse. Unspoken speaker names were never inserted into the transcript, and topic or previous text was never copied into it.

A value outside its limit returns `400 INVALID_CONTEXT` before transcription starts, for example `topic must be at most 1600 characters (got 1601)`. With `format=transliterate`, write the context in Latin letters to match the output.

A value containing `<|` or `|>` is also rejected.

### Keyterms prompting

* Words or short phrases (`"HDFC Bank"`, `"खाता नंबर"`); mixed scripts are fine; spelling need not be exact.
* Send a JSON array (`["खाता","HDFC Bank"]`) or a comma-separated string. Use the JSON form when an item contains a comma.
* A listed word that is not spoken should not appear in the output.
* More than 200 items → `400 INVALID_CONTEXT`.
* In streaming **headers**, non-ASCII text must be JSON-escaped (`["\u0916\u093e\u0924\u093e"]`). A form field can carry it directly.

> [!WARNING]
>
> A model that was not trained on context can become **less** accurate when given one. Compare results with and without context on your own audio before relying on it.

### Keyterms prompting example

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form language_code=hi-IN \
  --form 'keyterms=["खाता","नंबर","HDFC Bank"]'
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
            "model": "prisma-v3.0",
            "language_code": "hi-IN",
            "keyterms": json.dumps(["खाता", "नंबर", "HDFC Bank"], ensure_ascii=False),
        },
        timeout=60,
    )
print(r.json()["transcript"])
```

### Topic and keyterms together

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form language_code=hi-IN \
  --form 'topic=Quarterly review of retail banking dues and card collections' \
  --form 'keyterms=["खाता","नंबर","HDFC Bank"]'
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
            "model": "prisma-v3.0",
            "language_code": "hi-IN",
            "topic": "Quarterly review of retail banking dues and card collections",
            "keyterms": json.dumps(["खाता", "नंबर", "HDFC Bank"], ensure_ascii=False),
        },
        timeout=60,
    )
print(r.json()["transcript"])
```

### Speaker names example

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@clip.wav \
  --form model=prisma-v3.0 \
  --form language_code=hi-IN \
  --form 'speaker_names=["Priya","Rahul"]'
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
            "model": "prisma-v3.0",
            "language_code": "hi-IN",
            "speaker_names": json.dumps(["Priya", "Rahul"]),
        },
        timeout=60,
    )
print(r.json()["transcript"])
```

### A long recording cut into pieces (`previous_text`)

Send the transcript of the previous piece with the next one. `previous_text` applies to the first part of that piece only.

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@part2.wav \
  --form model=prisma-v3.0 \
  --form language_code=hi-IN \
  --form 'previous_text=मेरा खाता नंबर एक दो तीन चार पाँच है'
```

```python theme={null}
import requests

previous = ""
for part in ["part1.wav", "part2.wav", "part3.wav"]:
    data = {"model": "prisma-v3.0", "language_code": "hi-IN"}
    if len(previous) >= 12:                      # minimum length for previous_text
        data["previous_text"] = previous
    with open(part, "rb") as f:
        r = requests.post(
            "https://api.vachana.ai/stt/v3",
            headers={"X-API-Key-ID": "<API_KEY>"},
            files={"audio_file": (part, f, "audio/wav")},
            data=data,
            timeout=60,
        )
    previous = r.json().get("transcript", "")
    print(part, "->", previous)
```

### All four kinds together

```bash theme={null}
curl --location "https://api.vachana.ai/stt/v3" \
  --header "X-API-Key-ID: <API_KEY>" \
  --form audio_file=@part2.wav \
  --form model=prisma-v3.0 \
  --form language_code=hi-IN \
  --form 'topic=Quarterly review of retail banking dues and card collections' \
  --form 'keyterms=["खाता","नंबर","HDFC Bank"]' \
  --form 'speaker_names=["Priya","Rahul"]' \
  --form 'previous_text=मेरा खाता नंबर एक दो तीन चार पाँच है'
```

```python theme={null}
import json
import requests

with open("part2.wav", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": "<API_KEY>"},
        files={"audio_file": ("part2.wav", f, "audio/wav")},
        data={
            "model": "prisma-v3.0",
            "language_code": "hi-IN",
            "topic": "Quarterly review of retail banking dues and card collections",
            "keyterms": json.dumps(["खाता", "नंबर", "HDFC Bank"], ensure_ascii=False),
            "speaker_names": json.dumps(["Priya", "Rahul"]),
            "previous_text": "मेरा खाता नंबर एक दो तीन चार पाँच है",
        },
        timeout=60,
    )
print(r.json()["transcript"])
```

### Compare with and without context

```python theme={null}
import json
import requests

def transcribe(extra):
    with open("clip.wav", "rb") as f:
        r = requests.post(
            "https://api.vachana.ai/stt/v3",
            headers={"X-API-Key-ID": "<API_KEY>"},
            files={"audio_file": ("clip.wav", f, "audio/wav")},
            data={"model": "prisma-v3.0", "language_code": "hi-IN", **extra},
            timeout=60,
        )
    return r.json()["transcript"]

plain = transcribe({})
hinted = transcribe({"keyterms": json.dumps(["HDFC Bank"], ensure_ascii=False)})
print("without:", plain)
print("with:   ", hinted)
```

**Streaming** — the same four fields, sent as connection headers:

```python theme={null}
import json

headers = {
    "x-api-key-id": "<API_KEY>",
    "model": "prisma-v3.0",
    "language_code": "hi-IN",
    "keyterms": json.dumps(["खाता", "HDFC Bank"]),   # json.dumps escapes non-ASCII for headers
    "topic": "A call about a savings account",       # optional
}
# change them mid-session (applies from the next utterance):
# await ws.send(json.dumps({"type": "update_settings", "bias": {"list": ["Vachana", "HDFC"]}}))
```

## How it differs from Prisma v2.5

If you already use [Prisma v2.5](https://docs.gnani.ai/api/STT/models/prisma-v2-5.md), this table shows what behaves differently on Prisma v3.0. Everything else you send today keeps working.

| Topic | Prisma v2.5 | Prisma v3.0 |
| - | - | - |
| **Languages** | The same ten languages | The same ten languages, plus `indic-auto` for automatic detection |
| **Choosing the language** | You always choose one `language_code` | `indic-auto`, or one to four language codes, in the same field. They are hints, not a lock |
| **Which language was heard** | Not reported | Reported in `detected_language_code` on every transcript, including when you send one language |
| **Ways to write the text** | `verbatim` and `transcribe` | `verbatim`, `transcribe` and `codemix` (REST, Realtime and Batch), and `transliterate` (REST and Realtime) |
| **Romanised (Latin-letter) output** | Not available | `format=transliterate` writes the whole `transcript` in Latin letters. See [Romanised output](#romanised-output-transliterate). |
| **Style when you omit `format`** (REST) | Always `verbatim` | Depends on the request. A fixed `hi-IN` or `en-IN` gives `transcribe` (digits). Everything else gives `verbatim`. Send `format` yourself to keep your current output. See [Output styles](#output-styles). |
| **Hints to improve accuracy** | `bias_list` and `bias_score`: single words, up to 100 | `keyterms` (up to 200 words or short phrases), `topic`, `previous_text` and `speaker_names`. `bias_list` is still accepted as the older name of `keyterms`, and `bias_score` is ignored. |
| **`itn_native_numerals`** | Supported | Has no effect on REST or when streaming. The model writes numbers itself. |
| **`output.literal`** | Included when number formatting changed the text | Not returned, on REST or when streaming. Do not depend on it. |
| **`model` value in responses** | `prisma-v2.5` | `prisma-v3.0`. Update any code that checks it. |
| **New errors** | The existing error types | New types such as `INVALID_CONTEXT` and `MODEL_UNSUPPORTED_LANGUAGE`, and a `504`. See [Error Reference](https://docs.gnani.ai/api/introduction/errors.md). |
| **Batch jobs** | `config.model` is `prisma-v2.5`. The language is identified per file, from up to three codes. | Set `config.model` to `prisma-v3.0`. The model identifies the language of each segment, from `indic-auto` or 1–4 codes, and there is no separate identification step. `format`, `keyterms`, `topic` and `speaker_names` are new. See [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md#prisma-v3-0-options). |

**Before you switch**, send a few representative recordings (with numbers, names and mixed-language speech) through both models using the same `format`, and compare the transcripts. Add `keyterms` or `topic` only after the plain result looks right, and compare again.

## What it does not do

These are limits of the model itself. They apply on every API (REST, Realtime and Batch) unless noted.

* **Word-level timestamps** (the time each word was spoken).
* **Speaker diarization by the model** (labelling who said what) on REST and Realtime. Batch jobs separate speakers in their own pipeline step; see [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md#configuration). Note that `speaker_names` is not diarization: it only helps the model spell names correctly.
* **Translation** into another language.
* **Multi-channel audio** on REST and Realtime. If your recording has several channels, mix it down to a single (mono) channel first. Batch has an `is_multi_channel` setting for true multi-channel audio.
* **Languages outside the ten listed above**, for example `as-IN`.

Some restrictions depend on how you send the audio:

* **REST** accepts clips of up to 30 seconds. Use the [Batch Jobs API](https://docs.gnani.ai/api/STTBatch/Introduction.md) for longer recordings.
* **Realtime streaming** does not offer token-by-token streaming. Use `keyterms`, `topic`, `previous_text` and `speaker_names` to give hints when streaming.

## Limits

These limits belong to the model's inputs. They apply to REST and Realtime. Batch has a few stricter ones, such as a 30-character minimum for `topic`; see [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md#context).

| What | Limit |
| - | - |
| Languages in `language_code` | 1 to 4 |
| `keyterms` | Up to 200 items |
| `topic` | Up to 1,600 characters, no minimum |
| `previous_text` | No minimum. Only the last 600 characters are used. |
| `speaker_names` | 1 to 4 names |

Audio length, accepted formats, streaming session length, request rates and the number of live sessions are on [Limits](https://docs.gnani.ai/api/STT/limits.md). The limits are the same for Prisma v3.0 and Prisma v2.5, including on Batch.

## Next steps

* [Models](https://docs.gnani.ai/api/STT/models/overview.md): all Speech-to-Text models and how to choose between them.
* [Speech-to-Text overview](https://docs.gnani.ai/api/STT/overview.md): what works on REST, Realtime and Batch.
* Reference: [REST](https://docs.gnani.ai/api/STT/speech-to-text.md), [Realtime](https://docs.gnani.ai/api/STT/stt-websocket.md) and [Batch](https://docs.gnani.ai/api/STTBatch/Introduction.md).
* [Error Reference](https://docs.gnani.ai/api/introduction/errors.md) and [Limits](https://docs.gnani.ai/api/STT/limits.md).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.