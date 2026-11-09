> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Speech-to-Text

> Turn speech into text with Gnani Prisma. Choose a model, then choose how to send your audio: REST, Realtime streaming or Batch.

## Overview

Speech-to-Text (STT) turns spoken audio into written text in Indian languages and English. Using it involves two separate choices:

1. **A model.** Gnani Prisma is the model family. Prisma v3.0 and Prisma v2.5 are versions of it. See [Models](https://docs.gnani.ai/api/STT/models/overview.md).
2. **An access method.** This is how your audio reaches the model: REST, Realtime streaming or Batch.

Any model can be used with any access method.

## Choose how to send audio

| Access method | Use it when | What happens | Endpoint | Guide |
| - | - | - | - | - |
| **REST** | You have a short recording (up to 30 seconds) and want the transcript straight back. | You upload one file and the transcript is in the response. | `POST /stt/v3` | [REST transcription](https://docs.gnani.ai/api/STT/speech-to-text.md) |
| **Realtime streaming** | The audio is live, such as a phone call or a microphone. | You keep a WebSocket connection open and send audio as it is spoken. Transcripts arrive as each sentence finishes. | `WS /stt/v3/stream` | [Realtime streaming](https://docs.gnani.ai/api/STT/stt-websocket.md) |
| **Batch** | You have long recordings or many files and can wait for the results. | You create a job, it runs in the background, and you collect the transcripts when it is done. | `POST /stt/v3/batch/jobs` | [Batch transcription](https://docs.gnani.ai/api/STTBatch/Introduction.md) |

## Choose a model

| Model | Best for | Select it with |
| - | - | - |
| [**Prisma v3.0**](https://docs.gnani.ai/api/STT/models/prisma-v3.md) | Multilingual audio, automatic language detection, speech that mixes languages, and hints such as names and topics | `model=prisma-v3.0` |
| [**Prisma v2.5**](https://docs.gnani.ai/api/STT/models/prisma-v2-5.md) (default) | Transcribing in the language or languages you specify. | `model=prisma-v2.5` or leave out model |

All models and details are on the [Models](https://docs.gnani.ai/api/STT/models/overview.md) page.

> [!NOTE]
>
> **The `3` in `/stt/v3` is the URL version, not the model version.** Prisma v2.5 and Prisma v3.0 are both served from `/stt/v3`. Only the `model` value decides which model runs.

## What works where

In the table, **Prisma v3.0** or **Prisma v2.5** names the model that offers the feature. A dash means the feature is not available on that access method.

| | REST | Realtime streaming | Batch |
| - | - | - | - |
| **Select Prisma v2.5** | `model=prisma-v2.5` or leave out `model` | `model=prisma-v2.5` or leave out `model` | `config.model: prisma-v2.5` |
| **Select Prisma v3.0** | `model=prisma-v3.0` | `model: prisma-v3.0` | `config.model: prisma-v3.0` |
| **Language detection** (`indic-auto`, or 1–4 languages) | Prisma v3.0 | Prisma v3.0 | Prisma v3.0 |
| **`codemix` output style** | Prisma v3.0 | Prisma v3.0 | Prisma v3.0 |
| **`transliterate` output style** (transcript in Latin letters) | Prisma v3.0 | Prisma v3.0 | — |
| **Context hints** (keyterms, topic, previous text, speaker names) | Prisma v3.0 | Prisma v3.0 | Prisma v3.0, all except `previous_text` |
| **Speaker diarization** | — | — | Prisma v2.5, Prisma v3.0 |

The limits are the same for both models. See [Limits](https://docs.gnani.ai/api/STT/limits.md).

## Next steps

* [Models](https://docs.gnani.ai/api/STT/models/overview.md) and [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md).
* [Supported languages](https://docs.gnani.ai/api/STT/languages.md).
* [Limits](https://docs.gnani.ai/api/STT/limits.md).
* [Error Reference](https://docs.gnani.ai/api/introduction/errors.md).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.