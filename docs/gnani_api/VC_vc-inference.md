> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Voice Cloned TTS (REST)

> Generate cloned voice audio in a single synchronous response.

## Overview

**1. Step 1 — Generate a voice embedding**

Upload a reference audio clip to get a `speaker_embedding`. See [Voice Clone Embeddings](https://docs.gnani.ai/api/VC/voice-clone-embeddings.md).

**2. Step 2 — Synthesize with your cloned voice — this page**

Pass the `speaker_embedding` from Step 1 to this endpoint to synthesize audio in your cloned voice.

Synthesize audio using your cloned voice. Pass the `speaker_embedding` obtained from [Voice Clone Embeddings](https://docs.gnani.ai/api/VC/voice-clone-embeddings.md) along with your text. The full audio is returned in one response. For streaming playback, see [Voice Cloning Streaming](https://docs.gnani.ai/api/VC/vc-sse.md) or [Voice Cloning Realtime](https://docs.gnani.ai/api/VC/vc-websocket.md).

## Endpoint

```
POST https://api.vachana.ai/api/v1/tts/inference
```

## Authentication

| Header | Required | Description | Example |
| - | - | - | - |
| `X-API-Key-ID` | Yes | Your API key for authentication | `your-api-key-id` |
| `Content-Type` | Yes | Must be `application/json` | `application/json` |

## Request Body

**text** `string` *required*

The text to synthesize into speech

**model** `string`

Voice cloning model. Use `vachana-vc-v1`. Automatically set when `speaker_embedding` is provided — you may omit this field.

**audio\_config** `object` *required*

Audio output configuration

**properties**

**sample\_rate** `integer`

Sample rate in Hz (8000-44100)

**num\_channels** `integer`

Number of audio channels (1-8)

**sample\_width** `integer`

Sample width in bytes (1-4)

**encoding** `string`

Audio encoding format.

| Value | Meaning |
| - | - |
| `linear_pcm` | Uncompressed PCM audio |
| `oggopus` | OGG Opus |

**container** `string`

Audio container format.

| Value | Output |
| - | - |
| `wav` | WAV file |
| `raw` | Raw audio with no header |
| `mp3` | MP3 file. `bitrate` applies. |
| `ogg` | OGG Opus file |
| `mulaw` | G.711 µ-law |

**bitrate** `string`

MP3 bitrate. Only used when `container` is `mp3`.

| Value | Trade-off |
| - | - |
| `96k` | Smallest file of the three |
| `128k` | Standard quality |
| `192k` | Highest quality, largest file |

**speaker\_embedding** `object` *required*

Voice clone embedding obtained from the Voice Clone Embeddings endpoint

**properties**

**embedding** `string` *required*

The voice clone embedding string

**shape** `array` *required*

Shape of the embedding tensor, e.g., `[1, 768]`

**dtype** `string` *required*

Data type of the embedding, e.g., `torch.bfloat16`

## Response

Returns binary audio data in the format specified by `audio_config.container`:

* `audio/wav` for WAV files
* `audio/mpeg` for MP3 files
* `audio/ogg` for OGG files

## Example Request

```bash cURL theme={null}
curl -X POST https://api.vachana.ai/api/v1/tts/inference \
  -H "X-API-Key-ID: your-api-key-id" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "नमस्ते, आप कैसे हैं?",
    "model": "vachana-vc-v1",
    "audio_config": {
      "sample_rate": 44100,
      "encoding": "linear_pcm",
      "container": "wav"
    },
    "speaker_embedding": {
      "embedding": "your-embedding-string",
      "shape": [1, 768],
      "dtype": "torch.bfloat16"
    }
  }' \
  --output audio.wav
```

```python Python theme={null}
import requests

url = "https://api.vachana.ai/api/v1/tts/inference"
headers = {
    "X-API-Key-ID": "your-api-key-id",
    "Content-Type": "application/json"
}
payload = {
    "text": "नमस्ते, आप कैसे हैं?",
    "model": "vachana-vc-v1",
    "audio_config": {
        "sample_rate": 44100,
        "encoding": "linear_pcm",
        "container": "wav"
    },
    "speaker_embedding": {
        "embedding": "your-embedding-string",
        "shape": [1, 768],
        "dtype": "torch.bfloat16"
    }
}

response = requests.post(url, headers=headers, json=payload)

if response.status_code == 200:
    with open("audio.wav", "wb") as f:
        f.write(response.content)
    print("Audio saved successfully")
else:
    print(f"Error: {response.status_code}")
    print(response.json())
```

```javascript JavaScript theme={null}
const url = "https://api.vachana.ai/api/v1/tts/inference";
const headers = {
  "X-API-Key-ID": "your-api-key-id",
  "Content-Type": "application/json"
};
const payload = {
  text: "नमस्ते, आप कैसे हैं?",
  model: "vachana-vc-v1",
  audio_config: {
    sample_rate: 44100,
    encoding: "linear_pcm",
    container: "wav"
  },
  speaker_embedding: {
    embedding: "your-embedding-string",
    shape: [1, 768],
    dtype: "torch.bfloat16"
  }
};

fetch(url, {
  method: "POST",
  headers: headers,
  body: JSON.stringify(payload)
})
  .then(response => response.blob())
  .then(blob => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "audio.wav";
    a.click();
  })
  .catch(error => console.error("Error:", error));
```

## Error Responses

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

See [Error Reference](https://docs.gnani.ai/api/introduction/errors.md) for all Speech API errors.


## OpenAPI

````yaml VC.yml POST /api/v1/tts/inference
openapi: 3.1.0
info:
  title: Voice Cloned TTS Server
  description: >-
    Voice Cloning Text-to-Speech API — synthesize audio with a cloned voice via
    REST or SSE.
  version: 1.0.0
servers:
  - url: https://api.vachana.ai
    description: Production server
security: []
paths:
  /api/v1/tts/inference:
    post:
      summary: Voice Cloned TTS Inference
      operationId: vc_inference_api_v1_tts_inference_post
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
              $ref: '#/components/schemas/VoiceCloneRequest'
      responses:
        '200':
          description: Successful audio synthesis
          content:
            audio/wav:
              schema:
                type: string
                format: binary
            audio/mpeg:
              schema:
                type: string
                format: binary
            audio/ogg:
              schema:
                type: string
                format: binary
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
    VoiceCloneRequest:
      type: object
      title: VoiceCloneRequest
      description: Request body for voice cloned TTS inference.
      required:
        - text
        - speaker_embedding
        - audio_config
      properties:
        text:
          type: string
          title: Text
          description: The text to synthesize into speech.
        model:
          allOf:
            - $ref: '#/components/schemas/VCModel'
          description: >-
            Voice cloning model. Automatically set to `vachana-vc-v1` when
            `speaker_embedding` is provided.
        speaker_embedding:
          allOf:
            - $ref: '#/components/schemas/SpeakerEmbedding'
          description: Voice clone embedding from the Voice Clone Embeddings endpoint.
        audio_config:
          allOf:
            - $ref: '#/components/schemas/AudioConfig'
          description: Audio output configuration.
      example:
        text: नमस्ते, आप कैसे हैं?
        model: vachana-vc-v1
        speaker_embedding:
          embedding: <base64-encoded embedding>
          shape:
            - 1
            - 768
          dtype: torch.bfloat16
        audio_config:
          sample_rate: 44100
          num_channels: 1
          sample_width: 2
          encoding: linear_pcm
          container: wav
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
    StandardErrorResponse:
      type: object
      properties:
        success:
          type: boolean
          example: false
        error:
          $ref: '#/components/schemas/ErrorDetail'
    VCModel:
      type: string
      enum:
        - vachana-vc-v1
      title: VCModel
      description: Supported voice cloning model.
    SpeakerEmbedding:
      type: object
      title: SpeakerEmbedding
      description: Voice clone embedding obtained from the Voice Clone Embeddings endpoint.
      properties:
        embedding:
          type: string
          title: Embedding
          description: The base64-encoded voice clone embedding tensor.
        shape:
          type: array
          items:
            type: integer
          title: Shape
          description: Shape of the embedding tensor, e.g. [1, 768].
        dtype:
          type: string
          title: Dtype
          description: Data type of the embedding tensor, e.g. torch.bfloat16.
      required:
        - embedding
        - shape
        - dtype
    AudioConfig:
      properties:
        sample_rate:
          type: integer
          maximum: 44100
          minimum: 8000
          title: Sample Rate
          description: Sample rate in Hz
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
        - oggopus
      title: AudioEncoding
      description: Supported audio encodings.
    AudioContainer:
      type: string
      enum:
        - raw
        - mp3
        - wav
        - mulaw
        - ogg
      title: AudioContainer
      description: Supported audio containers.
    MP3Bitrate:
      type: string
      enum:
        - 96k
        - 128k
        - 192k
      title: MP3Bitrate
      description: Supported MP3 bitrate options (only used when container is mp3).

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.