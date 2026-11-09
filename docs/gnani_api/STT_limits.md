> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Limits

> Audio, request and session limits for Speech-to-Text.

## Limits

Current request-rate and concurrent-session limits for your account are available at [app.gnani.ai](https://app.gnani.ai). Numbers will be listed on this page later.

| Item | Prisma v3.0 | Prisma v2.5 |
| - | - | - |
| Audio length per request (**REST only**) | **30 s** | **30 s** |
| Shortest accepted audio | 0.1 s (shorter audio returns an empty transcript) | n/a |
| Audio formats (REST) | wav, mp3, ogg, flac, aac, m4a, detected from the file-name extension | Same |
| Languages in `language_code` | `indic-auto`, or 1–4 distinct, comma-separated | 1 (Batch: up to 3) |
| `keyterms` | Up to 200 words or short phrases (`bias_list`: 100 single words) | `bias_list`: 100 single words |
| `topic` | Up to 1,600 characters, no minimum (REST). Batch: 30–1,600 characters. | n/a |
| `previous_text` | No minimum (last 600 characters kept). REST only. | n/a |
| `speaker_names` | 1–4 names | n/a |
| `substitution_map` | 10 rules; patterns up to 200 characters | Same |
| Streaming session length (Realtime has no per-clip audio limit) | 15 minutes | 15 minutes |
| Streaming idle timeout | 60 s by default; set `x-idle-timeout-sec` (5–900) | n/a |
| Concurrent streaming sessions | A per-organisation cap applies. A rejected connection receives an `error` message that names the limit. | Same |
| Too many requests | Returns `429` with `error_code` `RATE_LIMITED`; wait and retry with backoff (see [Error Reference](https://docs.gnani.ai/api/introduction/errors.md)) | Same |
| Batch (no REST clip limit) | Up to 4 h per file, 100 files per upload job, 10 MB per uploaded file. Up to 5 GiB per file with a presigned upload. See [Batch STT limits](https://docs.gnani.ai/api/STTBatch/Introduction.md#limits). | Same |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.