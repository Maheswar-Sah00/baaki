> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Supported languages

> The languages supported by each Speech-to-Text model.

## Supported languages

Prisma v2.5 and Prisma v3.0 support these languages. The same list applies on REST, Realtime and Batch.

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


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.