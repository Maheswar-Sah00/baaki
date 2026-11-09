> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Text-to-Speech (Streaming)

> Stream audio in chunks as it's generated via Server-Sent Events.

## Overview

> [!TIP]
>
> **New — [Audio Tags](https://docs.gnani.ai/api/TTS/tts-audio-tags.md):** Add expressive delivery on Timbre v3.0 by placing tags like `<whispers>`, `<laugh>`, or `<pauses>` inline in your text.

Receive audio in chunks as it's generated, allowing playback to start immediately. Reduces latency compared to [TTS REST](https://docs.gnani.ai/api/TTS/tts-inference.md). For the lowest latency, see [TTS Realtime](https://docs.gnani.ai/api/TTS/tts-websocket.md).

> [!NOTE]
>
> Passing numbers, IDs, dates, or currency as raw strings causes mispronunciations. See the [Input Formatting Guide](https://docs.gnani.ai/api/TTS/tts-input-formating.md) for correct formatting of phone numbers, account numbers, PINs, Aadhaar, vehicle registration numbers, GSTIN, currency, and more.

***

## Models

| Model | `model` value | Languages | Extra parameters |
| :- | :- | :- | :- |
| Timbre v3.0 | `timbre-v3.0` | 10 Indian languages (every voice speaks all 10) | `language`, `speed`, [audio tags](https://docs.gnani.ai/api/TTS/tts-audio-tags.md) in `text` |
| Timbre v2.5 | `timbre-v2.5` | 10 Indian languages | `language`, `speed` |

**Supported languages:** Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, and Gujarati.

Each model has its own voices — see the [Voice Catalog](https://docs.gnani.ai/api/TTS/available-voices.md).

***

## Endpoint

```text theme={null}
POST https://api.vachana.ai/api/v1/tts/sse
```

***

## Authentication

| Header | Required | Description |
| :- | :- | :- |
| `X-API-Key-ID` | Yes | Your Gnani API key |

***

## Request Parameters

```json theme={null}
{
  "text": "नमस्ते, आप कैसे हैं?",
  "voice": "Nalini",
  "model": "timbre-v2.5",
  "language": "hi-IN",
  "speed": 1.0,
  "audio_config": {
    "sample_rate": 48000,
    "num_channels": 1,
    "sample_width": 2,
    "encoding": "linear_pcm",
    "container": "wav"
  }
}
```

**text** `string` *required*

The text to synthesize into speech. Pass numbers, dates, and currency as spoken words to avoid mispronunciations — see [Input Formatting Guide](https://docs.gnani.ai/api/TTS/tts-input-formating.md).

**model** `string` *required*

`timbre-v2.5` or `timbre-v3.0`. The model determines which voices you can use.

**voice** `string` *required*

Voice name from the catalog of the model you selected — voices are not shared between models.

| `model` | Example voices | Full list |
| :- | :- | :- |
| `timbre-v2.5` | `Nalini`, `Kaveri`, `Deepak` | [Timbre v2.5 voices](https://docs.gnani.ai/api/TTS/available-voices.md#timbre-v2-5-voices) |
| `timbre-v3.0` | `Shivani`, `Avinash`, `Lakshmi` | [Timbre v3.0 voices](https://docs.gnani.ai/api/TTS/available-voices.md#timbre-v3-0-voices) |

**language** `string` *required*

Language of the input text. Controls text normalization and routing.

| Value | Language |
| :- | :- |
| `auto` | Auto-detect from script (recommended for mixed content) |
| `hi-IN` | Hindi |
| `en-IN` | English |
| `ta-IN` | Tamil |
| `te-IN` | Telugu |
| `kn-IN` | Kannada |
| `ml-IN` | Malayalam |
| `mr-IN` | Marathi |
| `pa-IN` | Punjabi |
| `bn-IN` | Bengali |
| `gu-IN` | Gujarati |
| `hi-en` | Hinglish (code-mixed Hindi–English) |

**speed** `number | string` (default: 1.0)

Playback speed multiplier. Numeric range: `0.85` (slowest) to `1.15` (fastest). String shortcuts: `"slow"` = 0.85, `"medium"` = 1.0, `"fast"` = 1.15.

**audio\_config** `object`

Controls the format of the returned audio.

**audio\_config fields**

**audio\_config.sample\_rate** `integer` (default: 48000)

Sample rate in Hz. Supported: `8000`, `16000`, `22050`, `24000`, `44100`, `48000`.

**audio\_config.num\_channels** `integer` (default: 1)

Number of audio channels. `1` for mono.

**audio\_config.sample\_width** `integer` (default: 2)

Sample width in bytes. `2` for 16-bit audio.

**audio\_config.encoding** `string` (default: linear\_pcm)

Audio encoding format. For telephony, prefer `container=mulaw` or `container=alaw` over this field, as both produce the same output. Not required when `container` is `mp3`.

| Value | Meaning |
| - | - |
| `linear_pcm` (default) | Uncompressed PCM audio |
| `pcm_s16le` | Signed 16-bit little-endian PCM |
| `pcm_mulaw` | G.711 µ-law. With `container=raw`, the same as `container=mulaw`. |
| `pcm_alaw` | G.711 A-law. With `container=raw`, the same as `container=alaw`. |
| `oggopus` | OGG Opus, a playable file. The same as `container=ogg`. |

**audio\_config.container** `string` (default: wav)

Output container format. See the [Audio Format Reference](#audio-format-reference) for sample rates and content types.

| Value | Output |
| - | - |
| `wav` (default) | WAV file, with header |
| `raw` | Raw audio with no header (16-bit PCM with `linear_pcm`) |
| `mp3` | MP3 file. `bitrate` applies. |
| `ogg` | OGG Opus file |
| `mulaw` | Raw G.711 µ-law. Forces 8000 Hz. |
| `alaw` | Raw G.711 A-law. Forces 8000 Hz. |

**audio\_config.bitrate** `string` (default: 128k)

MP3 bitrate. Only used when `container` is `mp3`.

| Value | Trade-off |
| - | - |
| `32k` | Lowest quality, smallest file |
| `64k` | Lower quality, smaller file |
| `96k` | Medium |
| `128k` (default) | Standard quality |
| `192k` | Highest quality, largest file |

***

## Audio Format Reference

| `container` | `encoding` | Output | `sample_rate` | `bitrate` | Content-Type |
| - | - | - | - | - | - |
| `wav` | `linear_pcm` | WAV file (with header) | 8000–48000 Hz | — | `audio/wav` |
| `raw` | `linear_pcm` | Raw 16-bit PCM | 8000–48000 Hz | — | `application/octet-stream` |
| `mp3` | — | MP3 file | 8000–48000 Hz | `32k`–`192k` | `audio/mpeg` |
| `ogg` | — | OGG Opus file | 8000–48000 Hz | — | `audio/ogg` |
| `mulaw` | — | Raw G.711 µ-law | **forced 8000 Hz** | — | `audio/basic` |
| `alaw` | — | Raw G.711 A-law | **forced 8000 Hz** | — | `audio/alaw` |

**Encoding aliases** — produce identical output to the `container` rows above:

| `container` | `encoding` | Equivalent to |
| - | - | - |
| `raw` | `pcm_mulaw` | `container=mulaw` |
| `raw` | `pcm_alaw` | `container=alaw` |
| `raw` or `ogg` | `oggopus` | `container=ogg` |

`bitrate` only applies when `container=mp3`. `container=mulaw`/`alaw` override `sample_rate` to 8000 Hz.

> [!NOTE]
>
> When `container=ogg` or `encoding=oggopus` is requested, all audio chunks are encoded into a single OGG Opus file delivered as one chunk — streaming delivery is not possible for OGG.

***

## Response

The server streams audio via Server-Sent Events. Each `chunk` event carries base64-encoded audio in the `audio` field. A final `complete` event signals that synthesis is finished.

```text theme={null}
event: start
data: {"status": "streaming_started", "text": "नमस्ते, आप कैसे हैं?"}

event: chunk
data: {"chunk_index": 1, "audio": "<base64-encoded audio>", "is_final": false}

event: chunk
data: {"chunk_index": 2, "audio": "<base64-encoded audio>", "is_final": false}

event: complete
data: {"chunk_index": 3, "audio": "", "is_final": true}
```

| Event | Description |
| :- | :- |
| `start` | Synthesis has begun. |
| `chunk` | An audio fragment. Decode `audio` from base64 and append to your buffer in order. |
| `complete` | All audio has been sent. `is_final: true`, `audio` is empty. |
| `error` | Synthesis failed. Contains error details when returned by the server. |

### Errors

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

***

## Code Example

```bash cURL theme={null}
curl -X POST https://api.vachana.ai/api/v1/tts/sse \
  -H "Content-Type: application/json" \
  -H "X-API-Key-ID: <your-api-key>" \
  -d '{
    "text": "नमस्ते, आप कैसे हैं?",
    "voice": "Nalini",
    "model": "timbre-v2.5",
    "language": "hi-IN",
    "speed": 1.0,
    "audio_config": {
      "sample_rate": 48000,
      "encoding": "linear_pcm",
      "container": "wav"
    }
  }'
```

```javascript JavaScript theme={null}
const response = await fetch("https://api.vachana.ai/api/v1/tts/sse", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key-ID": "<your-api-key>",
  },
  body: JSON.stringify({
    text: "नमस्ते, आप कैसे हैं?",
    voice: "Nalini",
    model: "timbre-v2.5",
    language: "hi-IN",
    speed: 1.0,
    audio_config: {
      sample_rate: 48000,
      encoding: "linear_pcm",
      container: "wav",
    },
  }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  console.log(decoder.decode(value));
}
```

```python Python theme={null}
import requests, base64

response = requests.post(
    "https://api.vachana.ai/api/v1/tts/sse",
    headers={
        "Content-Type": "application/json",
        "X-API-Key-ID": "<your-api-key>",
    },
    json={
        "text": "नमस्ते, आप कैसे हैं?",
        "voice": "Nalini",
        "model": "timbre-v2.5",
        "language": "hi-IN",
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    },
    stream=True,
)

for line in response.iter_lines():
    if line:
        print(line.decode("utf-8"))
```

***

## Available Voices

Each model has its own voices, and a voice only works with its own model:

* **Timbre v2.5** — 42 voices across 10 Indian languages, English, and Hinglish, each with a preferred language. See [Timbre v2.5 voices](https://docs.gnani.ai/api/TTS/available-voices.md#timbre-v2-5-voices).
* **Timbre v3.0** — 13 voices that each speak all 10 languages and support audio tags. See [Timbre v3.0 voices](https://docs.gnani.ai/api/TTS/available-voices.md#timbre-v3-0-voices).

Popular examples: `Nalini` (Hindi), `Kaveri` (English), `Deepak` (Hindi), `Poorvi` (Hinglish).

***

## Python SDK

The SDK's streaming client handles SSE parsing and chunk reassembly for you — you just iterate and write.

### Installation

```bash theme={null}
pip install gnani-vachana
```

Requires **Python 3.10+**.

### Authentication

```python Constructor argument theme={null}
from gnani.tts import GnaniTTSStreamClient

client = GnaniTTSStreamClient(api_key="your-api-key")
```

```bash Environment variable theme={null}
export GNANI_API_KEY="your-api-key"
```

```python Environment variable (usage) theme={null}
from gnani.tts import GnaniTTSStreamClient

client = GnaniTTSStreamClient()
```

### Stream Audio to a File

`synthesize_stream` yields audio chunks as they arrive. Playback or writing can begin before the full response is complete.

```python theme={null}
from gnani.tts import GnaniTTSStreamClient

client = GnaniTTSStreamClient(api_key="your-api-key")

with open("output.wav", "wb") as f:
    for chunk in client.synthesize_stream(
        "नमस्ते, आप कैसे हैं?",
        voice="Nalini",
        model="timbre-v2.5",
        language="hi-IN",
    ):
        f.write(chunk)
```

### With Custom Audio Config

```python theme={null}
from gnani.tts import GnaniTTSStreamClient, AudioConfig

client = GnaniTTSStreamClient(api_key="your-api-key")

with open("output.wav", "wb") as f:
    for chunk in client.synthesize_stream(
        "नमस्ते, आप कैसे हैं?",
        voice="Nalini",
        model="timbre-v2.5",
        language="hi-IN",
        audio_config=AudioConfig(
            sample_rate=48000,
            encoding="linear_pcm",
            container="wav",
        ),
    ):
        f.write(chunk)
```


## OpenAPI

````yaml POST /api/v1/tts/sse
openapi: 3.1.0
info:
  title: TTS Server
  description: Text-to-Speech API with WebSocket, SSE and gRPC streaming support
  version: 1.0.0
servers:
  - url: https://api.vachana.ai
    description: Production server
security: []
paths:
  /api/v1/tts/sse:
    post:
      summary: TTS Stream
      operationId: tts_stream_api_v1_tts_sse_post
      parameters:
        - name: X-API-Key-ID
          in: header
          required: true
          schema:
            anyOf:
              - type: string
            title: X-Api-Key-Id
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TextToSpeechRequest'
      responses:
        '200':
          description: Successful Server-Sent Events stream
          content:
            text/event-stream:
              schema:
                type: string
              example: |-
                event: start
                data: {"status": "streaming_started", "text": "Hello"}

                event: chunk
                data: {"chunk_index": 1, "audio": "<base64>", "is_final": false}

                event: complete
                data: {"chunk_index": 2, "audio": "", "is_final": true}
        '400':
          description: Bad Request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/FlatErrorResponse'
              example:
                success: false
                message: 'Invalid request: Field required at body -> text'
                status_code: 400
        '403':
          description: Forbidden
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StandardErrorResponse'
              example:
                success: false
                error:
                  type: FORBIDDEN
                  message: >-
                    You do not have permission to access this resource. Check
                    your API key, organization status, or available credits.
        '429':
          description: Too Many Requests
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GatewayErrorResponse'
              example:
                detail:
                  error_code: RATE_LIMITED
                  message: >-
                    Only 1 active request is allowed at a time. Wait for your
                    current request to finish before sending another.
                  status_code: 429
        '500':
          description: Internal Server Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/FlatErrorResponse'
              example:
                success: false
                message: We are facing technical difficulties. Please try again later.
                status_code: 500
        '503':
          description: Service Unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StandardErrorResponse'
              example:
                success: false
                error:
                  type: SERVICE_UNAVAILABLE
                  message: Text-to-speech service is temporarily unavailable.
components:
  schemas:
    TextToSpeechRequest:
      properties:
        text:
          type: string
          title: Text
          description: >-
            Text to synthesize. With `timbre-v3.0` the text may carry inline
            audio tags: `<coughs>`, `<excited>`, `<exhales>`, `<giggle>`,
            `<laugh>`, `<pauses>`, `<shouting>`, `<sigh>`, `<slow>`,
            `<sniffles>`, `<whispers>`, `<yawns>`, `<clears throat>` — for
            example `Let me check. <pauses> Found it <laugh>`. With
            `timbre-v2.5` these tags are removed before synthesis and are not
            spoken; text consisting only of tags is rejected with 400.
        voice:
          type: string
          title: Voice
          description: >-
            Voice name from the catalog of the requested model. `timbre-v3.0`
            voices: Avinash, Shivani, Lakshmi, Kalpana, Shubham, Prakash,
            Devansh, Yashraj, Chetana, Vasudha, Riyaa, Tarika and Harshad (each
            speaks all supported languages).
        model:
          allOf:
            - $ref: '#/components/schemas/TTSModel'
        language:
          type: string
          title: Language
          description: >-
            Language code. Use `auto`, `hi-IN`, `en-IN`, `hi-en`, `ta-IN`,
            `te-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `pa-IN`, `bn-IN`, or `gu-IN`.
        speed:
          type: number
          title: Speed
          description: 'Playback speed multiplier. Range: 0.85–1.15.'
        audio_config:
          allOf:
            - $ref: '#/components/schemas/AudioConfig'
      type: object
      required:
        - text
        - model
        - audio_config
      title: TextToSpeechRequest
      description: Request body for TTS inference.
      example:
        text: नमस्ते, आप कैसे हैं?
        voice: Nalini
        model: timbre-v2.5
        language: hi-IN
        speed: 1
        audio_config:
          encoding: linear_pcm
          container: wav
          num_channels: 1
          sample_rate: 48000
          sample_width: 2
    FlatErrorResponse:
      type: object
      description: Error body returned for invalid requests and unexpected failures.
      properties:
        success:
          type: boolean
          example: false
        message:
          type: string
          description: What went wrong.
        status_code:
          type: integer
          description: The HTTP status code.
    StandardErrorResponse:
      type: object
      properties:
        success:
          type: boolean
          example: false
        error:
          $ref: '#/components/schemas/ErrorDetail'
    GatewayErrorResponse:
      type: object
      description: Authentication and rate-limit errors (401, 403, 429).
      properties:
        detail:
          type: object
          properties:
            error_code:
              type: string
              description: >-
                One of `MISSING_API_KEY`, `INVALID_API_KEY`,
                `SCOPE_NOT_ALLOWED`, `RATE_LIMITED`.
            message:
              type: string
            status_code:
              type: integer
    TTSModel:
      type: string
      enum:
        - timbre-v2.5
        - timbre-v3.0
      title: TTSModel
      description: >-
        TTS model: `timbre-v2.5` or `timbre-v3.0`. Each model has its own voice
        catalog, and a voice from one cannot be used with the other.
        `timbre-v3.0` additionally supports inline audio tags in `text`.
    AudioConfig:
      properties:
        sample_rate:
          type: integer
          maximum: 48000
          minimum: 8000
          title: Sample Rate
          description: >-
            Sample rate in Hz. Supported: 8000, 16000, 22050, 24000, 44100,
            48000
        num_channels:
          type: integer
          maximum: 8
          minimum: 1
          title: Num Channels
          description: Number of audio channels
        sample_width:
          type: integer
          maximum: 4
          minimum: 1
          title: Sample Width
          description: Sample width in bytes
        encoding:
          allOf:
            - $ref: '#/components/schemas/AudioEncoding'
          description: Audio encoding format
        container:
          allOf:
            - $ref: '#/components/schemas/AudioContainer'
          description: Audio container format
        bitrate:
          allOf:
            - $ref: '#/components/schemas/MP3Bitrate'
          description: MP3 bitrate (only used when container=mp3)
      type: object
      title: AudioConfig
      description: Audio output configuration.
    ErrorDetail:
      type: object
      properties:
        type:
          type: string
          description: A short error code string (e.g., 'INVALID_REQUEST_ERROR').
        message:
          type: string
          description: A descriptive error message.
    AudioEncoding:
      type: string
      enum:
        - linear_pcm
        - pcm_s16le
        - pcm_mulaw
        - pcm_alaw
        - oggopus
      title: AudioEncoding
      description: >-
        Supported audio encodings. Use pcm_mulaw or pcm_alaw for G.711 telephony
        codecs (forces 8000 Hz output). Use oggopus or set container=ogg to
        receive a playable OGG Opus file.
    AudioContainer:
      type: string
      enum:
        - raw
        - mp3
        - wav
        - mulaw
        - alaw
        - ogg
      title: AudioContainer
      description: Supported audio containers.
    MP3Bitrate:
      type: string
      enum:
        - 32k
        - 64k
        - 96k
        - 128k
        - 192k
      title: MP3Bitrate
      description: >-
        Supported MP3 bitrate options (only used when container is MP3).
        Default: 128k

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.