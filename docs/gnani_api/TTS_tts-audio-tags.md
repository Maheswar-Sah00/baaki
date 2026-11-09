> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Audio Tags

> Add expressive delivery to Timbre v3.0 speech using inline audio tags.

## Overview

Timbre v3.0 renders expression from inline tags — `<tag>` placed directly in the `text` field. Each tag changes delivery from its position to the end of the input.

Tags are optional. Text without any tag plays in a neutral tone.

> [!TIP]
>
> Audio tags are supported on `timbre-v3.0` only. With `timbre-v2.5` they are removed from the text before synthesis and are not spoken; a request whose text contains only tags is rejected with `400 Bad Request`.

***

## Syntax and Scope

Place a tag anywhere in the `text` field using angle-bracket syntax:

```
<tag>
```

**Tag names are case-sensitive** and must match the catalog exactly — including spaces, hyphens, and underscores.

```
<laugh>   ✅ correct
<Laughs Harder>   ❌ wrong case
[laughs harder]   ❌ wrong bracket style
```

**Scope:** a tag applies from its position to the **end of the input** (or until the next tag). There is no closing tag.

```
Please hold. <whispers> Your order is almost ready. <whispers> Thank you for your patience.
```

In this example: "Please hold." is delivered in the default (neutral) tone, "Your order is almost ready." is whispered, and "Thank you for your patience." uses a soft, quiet tone.

***

## Supported Tags

13 tags are supported in Timbre v3.0. Use them inline to change how specific parts of your text are delivered.

| Tag | Category | Effect |
| :- | :- | :- |
| `<laugh>` | Laughter | Full laugh |
| `<giggle>` | Laughter | Light, high-pitched giggle |
| `<sigh>` | Breath | Audible sigh |
| `<exhales>` | Breath | Audible exhale |
| `<sniffles>` | Breath | Sniffling |
| `<yawns>` | Breath | Yawning |
| `<coughs>` | Breath | Coughing |
| `<clears throat>` | Breath | Throat-clearing |
| `<whispers>` | Vocal | Hushed delivery |
| `<shouting>` | Vocal | Loud, raised voice |
| `<excited>` | Vocal | Energetic, enthusiastic delivery |
| `<slow>` | Pacing | Drawn-out delivery |
| `<pauses>` | Silence | Short silence — **not spoken aloud** |

> [!NOTE]
>
> `<pauses>` inserts silence. It is never read aloud — the voice stops briefly and then continues with the next word.

### Invalid tags

Unknown tags are **stripped silently** — the request succeeds and the tag text is never spoken.

***

## Code Examples

### Add a tag to a REST inference request

```bash cURL theme={null}
curl -X POST https://api.vachana.ai/api/v1/tts/inference \
  -H "Content-Type: application/json" \
  -H "X-API-Key-ID: <your-api-key>" \
  -d '{
    "text": "आपका ऑर्डर आ गया है! <giggle> बहुत अच्छा चुनाव किया आपने।",
    "voice": "Shivani",
    "model": "timbre-v3.0",
    "language": "hi-IN",
    "audio_config": {
      "sample_rate": 48000,
      "encoding": "linear_pcm",
      "container": "wav"
    }
  }' \
  --output response.wav
```

```python Python theme={null}
import requests

response = requests.post(
    "https://api.vachana.ai/api/v1/tts/inference",
    headers={
        "Content-Type": "application/json",
        "X-API-Key-ID": "<your-api-key>",
    },
    json={
        "text": "आपका ऑर्डर आ गया है! <giggle> बहुत अच्छा चुनाव किया आपने।",
        "voice": "Shivani",
        "model": "timbre-v3.0",
        "language": "hi-IN",
        "audio_config": {
            "sample_rate": 48000,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    },
)

with open("response.wav", "wb") as f:
    f.write(response.content)
```

```javascript JavaScript theme={null}
const response = await fetch("https://api.vachana.ai/api/v1/tts/inference", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key-ID": "<your-api-key>",
  },
  body: JSON.stringify({
    text: "आपका ऑर्डर आ गया है! <giggle> बहुत अच्छा चुनाव किया आपने।",
    voice: "Shivani",
    model: "timbre-v3.0",
    language: "hi-IN",
    audio_config: {
      sample_rate: 48000,
      encoding: "linear_pcm",
      container: "wav",
    },
  }),
});

const audio = await response.arrayBuffer();
```

### Multiple tags in one utterance

Tags chain — each one applies from its position until the next:

```bash cURL theme={null}
curl -X POST https://api.vachana.ai/api/v1/tts/inference \
  -H "Content-Type: application/json" \
  -H "X-API-Key-ID: <your-api-key>" \
  -d '{
    "text": "Attention all shoppers. <shouting> Sale ends in ten minutes! <whispers> Thank you for visiting us today.",
    "voice": "Avinash",
    "model": "timbre-v3.0",
    "language": "en-IN",
    "audio_config": {
      "sample_rate": 48000,
      "encoding": "linear_pcm",
      "container": "wav"
    }
  }' \
  --output response.wav
```

```python Python theme={null}
import requests

response = requests.post(
    "https://api.vachana.ai/api/v1/tts/inference",
    headers={
        "Content-Type": "application/json",
        "X-API-Key-ID": "<your-api-key>",
    },
    json={
        "text": "Attention all shoppers. <shouting> Sale ends in ten minutes! <whispers> Thank you for visiting us today.",
        "voice": "Avinash",
        "model": "timbre-v3.0",
        "language": "en-IN",
        "audio_config": {
            "sample_rate": 48000,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    },
)

with open("response.wav", "wb") as f:
    f.write(response.content)
```

```javascript JavaScript theme={null}
const response = await fetch("https://api.vachana.ai/api/v1/tts/inference", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key-ID": "<your-api-key>",
  },
  body: JSON.stringify({
    text: "Attention all shoppers. <shouting> Sale ends in ten minutes! <whispers> Thank you for visiting us today.",
    voice: "Avinash",
    model: "timbre-v3.0",
    language: "en-IN",
    audio_config: {
      sample_rate: 48000,
      encoding: "linear_pcm",
      container: "wav",
    },
  }),
});

const audio = await response.arrayBuffer();
```

### Add a pause between sentences

`<pauses>` inserts silence without speaking the tag:

```bash cURL theme={null}
curl -X POST https://api.vachana.ai/api/v1/tts/inference \
  -H "Content-Type: application/json" \
  -H "X-API-Key-ID: <your-api-key>" \
  -d '{
    "text": "Please enter your four digit PIN. <pauses> Got it. Processing your request now.",
    "voice": "Shivani",
    "model": "timbre-v3.0",
    "language": "hi-IN",
    "audio_config": {
      "sample_rate": 48000,
      "encoding": "linear_pcm",
      "container": "wav"
    }
  }' \
  --output response.wav
```

```python Python theme={null}
import requests

response = requests.post(
    "https://api.vachana.ai/api/v1/tts/inference",
    headers={
        "Content-Type": "application/json",
        "X-API-Key-ID": "<your-api-key>",
    },
    json={
        "text": "Please enter your four digit PIN. <pauses> Got it. Processing your request now.",
        "voice": "Shivani",
        "model": "timbre-v3.0",
        "language": "hi-IN",
        "audio_config": {
            "sample_rate": 48000,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    },
)

with open("response.wav", "wb") as f:
    f.write(response.content)
```

```javascript JavaScript theme={null}
const response = await fetch("https://api.vachana.ai/api/v1/tts/inference", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key-ID": "<your-api-key>",
  },
  body: JSON.stringify({
    text: "Please enter your four digit PIN. <pauses> Got it. Processing your request now.",
    voice: "Shivani",
    model: "timbre-v3.0",
    language: "hi-IN",
    audio_config: {
      sample_rate: 48000,
      encoding: "linear_pcm",
      container: "wav",
    },
  }),
});

const audio = await response.arrayBuffer();
```

### Streaming with tags (SSE)

Audio tags work identically on the SSE streaming endpoint. Tags that span a chunk boundary are still recognised correctly by the model.

```bash cURL theme={null}
curl -X POST https://api.vachana.ai/api/v1/tts/sse \
  -H "Content-Type: application/json" \
  -H "X-API-Key-ID: <your-api-key>" \
  -d '{
    "text": "Your package has been delivered! <whispers> Have a great day.",
    "voice": "Shivani",
    "model": "timbre-v3.0",
    "language": "hi-IN",
    "audio_config": {
      "sample_rate": 48000,
      "encoding": "linear_pcm",
      "container": "wav"
    }
  }'
```

```python Python theme={null}
import requests

response = requests.post(
    "https://api.vachana.ai/api/v1/tts/sse",
    headers={
        "Content-Type": "application/json",
        "X-API-Key-ID": "<your-api-key>",
    },
    json={
        "text": "Your package has been delivered! <whispers> Have a great day.",
        "voice": "Shivani",
        "model": "timbre-v3.0",
        "language": "hi-IN",
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

```javascript JavaScript theme={null}
const response = await fetch("https://api.vachana.ai/api/v1/tts/sse", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key-ID": "<your-api-key>",
  },
  body: JSON.stringify({
    text: "Your package has been delivered! <whispers> Have a great day.",
    voice: "Shivani",
    model: "timbre-v3.0",
    language: "hi-IN",
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

***

## Billing

Inline tags **count as billable characters**. The tag text (including the angle brackets) is included in the character count for the request.

For example, the text `Hello! <giggle> Great to hear from you.` is billed as 42 characters — the full string, tag included.

***

## Tips

* **One tag at a time** — chaining too many tags in a short text can produce unnatural transitions. Two or three tags per paragraph is a good baseline.
* **Silence tags before prompts** — `<pauses>` before an IVR prompt ("Please say yes or no.") gives callers time to respond and improves recognition accuracy.
* **Match the tag to the voice persona** — expressive tags (`<shouting>`, `<giggle>`) work best on voices with an Expressive or Friendly persona. Professional voices tend to moderate extreme tags.
* **Test before going live** — preview tagged text in the [Gnani TTS playground](https://app.gnani.ai/voice/text-to-speech) before integrating.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.