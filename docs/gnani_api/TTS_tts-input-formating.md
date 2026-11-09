> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Text Normalization Guide

> How the API automatically converts numbers, currency, dates, IDs, and more into natural spoken form.

## Overview

Text normalization (TN) is an automatic step that runs on every synthesis request before audio is generated. It converts written text — numbers, currency, dates, abbreviations, IDs, and more — into the natural spoken form that gets sent to the voice.

You don't need to pre-format most input. Write text naturally and TN handles it.

> [!TIP]
>
> Passing numbers, IDs, dates, or currency as raw strings is now handled automatically. The guide below documents exactly what gets converted and how, so you can predict the output and catch edge cases.

***

## Supported Languages

TN is active for all 10 supported languages. Select the language using the `language` parameter, or pass `auto` to detect it from the input script.

| `language` value | Language |
| :- | :- |
| `auto` | Auto-detected from the input script (default) |
| `hi` | Hindi |
| `en` | English |
| `mr` | Marathi |
| `ta` | Tamil |
| `te` | Telugu |
| `kn` | Kannada |
| `ml` | Malayalam |
| `gu` | Gujarati |
| `pa` | Punjabi |
| `bn` | Bengali |

> [!NOTE]
>
> English, Hindi, Marathi, and Tamil have the deepest coverage, including irregular number forms and compound constructions. The other six languages are fully supported — number and currency word choices are under continuous refinement, so occasional word-choice updates may arrive over time even though sentence structure is always correct.
>
> `hinglish` is **not** a valid `language` value. It appears only as an internal outcome of `auto` detection on code-mixed Devanagari + Latin text. Passing `language: "hinglish"` in a request is rejected.

### How `auto` detection works

When `language` is `auto`, the dominant script in your input determines the normalization profile:

| Script detected | Resolves to |
| :- | :- |
| Devanagari | Hindi (pass `mr` explicitly for Marathi) |
| Bengali script | Bengali |
| Gurmukhi | Punjabi |
| Gujarati script | Gujarati |
| Tamil script | Tamil |
| Telugu script | Telugu |
| Kannada script | Kannada |
| Malayalam script | Malayalam |
| Devanagari + Latin mixed | Hinglish (code-mixed) |
| No Indic script | English |

> [!WARNING]
>
> `auto` cannot select a non-English profile for text that contains no Indic script. A message that's entirely in Latin letters and digits (e.g. `"42"`) always normalizes as English under `auto`, even when synthesized in a non-English voice. Pass the language hint explicitly (e.g. `"kn"`) if you need native-language number reading for Latin-script input.

### English words that always stay in English

Regardless of the resolved language, these are always read in English — matching how they're spoken even in fluent Indic speech:

* Units of measurement (`kg`, `km`, `°C`, `GB`, etc.)
* `AM` / `PM`
* URLs and email addresses

The words **"point"** (decimals) and **"percent"** stay in English when `language` is `auto`. When you set a language explicitly, they localize — Hindi uses the formal register (दशमलव / प्रतिशत); all other languages use the colloquial loanword form (e.g. Kannada ಪಾಯಿಂಟ್ / ಪರ್ಸೆಂಟ್).

***

## How Normalization Works

Every synthesis request passes through the same ordered pipeline:

1. Inline markup (pause or speed tags) is stripped from the spoken output.
2. The target language profile is resolved from `language`, or auto-detected.
3. Honorifics are expanded (`Dr.` → Doctor / डॉक्टर).
4. Address and business abbreviations are expanded (`Rd` → Road, `Ltd` → Limited).
5. Numbers, currency, dates, times, and identifiers are normalized in a fixed rule order — more specific patterns (like a PAN number) are always claimed before general ones (like a bare digit run).
6. Common initialisms (`OTP`, `GST`, `EMI`, etc.) are spelled out letter-by-letter.
7. Natural pause commas are inserted for dense ID and phone patterns.

***

## Numbers

| Input | English | Hindi | Notes |
| :- | :- | :- | :- |
| `42` | forty two | बयालीस | Cardinal, localized per language |
| `-42` | negative forty two | minus बयालीस | English says "negative"; all other languages use the English word "minus" (not yet localized) |
| `12.5` | twelve point five | बारह दशमलव पाँच *(explicit)* / बारह point पाँच *(auto)* | "point" only localizes when language is set explicitly |
| `10,000` | ten thousand | दस हजार | Western grouping, read as one number |
| `2,40,000` | two lakh forty thousand | दो लाख चालीस हजार | Indian lakh-grouping is used for all languages including English |
| `5th` | fifth | पाँचवां | English ordinal suffix triggers native ordinal form |

### Cardinal numbers vs. digit-by-digit IDs

A bare number isn't always read as a quantity — context decides:

* **Quantity** — if the number follows a word like `iPhone`, `Class`, `Sector`, `Seat`, `Row`, or `Gate`, it's always read as a number (e.g. "iPhone fifteen", "Sector eleven").
* **Digit-by-digit** — triggered by context words like `account`, `OTP`, `card`, `PIN`, `Aadhaar`, or `PAN` near the number, or a run of 6+ digits, or exactly 4/6/10/12/16 digits.
* **Duration words** (`minutes`, `hours`, `days`) always force a quantity reading, even for digit runs that would otherwise look ID-like.

Only English compresses repeated digits when spelling IDs (`880044` → "double eight double zero double four"). Every other language spells each digit individually.

### Numeric ranges

An en-dash (–) between two numbers is read as "to":

| Input | English output |
| :- | :- |
| `3–5` | three to five |
| `5.7–6.4%` | five point seven to six point four percent |
| `25–29 Jun` | twenty five to twenty nine June |
| `8–10 AM` | eight to ten A M |

***

## Currency

| Input | English output | Notes |
| :- | :- | :- |
| `₹599` | five hundred ninety nine rupees | |
| `₹2,50,000` | two lakh fifty thousand rupees | Indian lakh/crore grouping honored |
| `₹4,312.50` | four thousand three hundred twelve rupees and fifty paise | Decimal reads as rupees + paise |
| `₹12.6 crore` | twelve point six crore rupees | Decimal reads as "point" before a magnitude word |
| `Rs. 500` / `Rs 500` | five hundred rupees | Reads identically to ₹500 |
| `$4.7 million` | four point seven million dollars | |

The rupee word localizes per language (रुपये in Hindi/Marathi, ரூபாய் in Tamil, etc.). Any currency symbol (`$`, `£`, `¥`, `€`, `¢`) is always expanded to a word — raw symbols never appear in the spoken output.

***

## Percentages

| Input | English | Hindi (explicit) | Kannada (explicit) |
| :- | :- | :- | :- |
| `8.5%` | eight point five percent | आठ दशमलव पाँच प्रतिशत | ಎಂಟು ಪಾಯಿಂಟ್ ಐದು ಪರ್ಸೆಂಟ್ |
| `7.5% p.a.` | seven point five percent per annum | — | `per annum` stays in English in all languages |

***

## Dates

Dates in `DD/MM/YYYY`, `DD-MM-YYYY`, and written-month formats (`25 Jun 2026`) are read in full and localized per language.

### Financial year and quarter references

| Input | English output |
| :- | :- |
| `FY2024-25` | financial year twenty twenty four twenty twenty five |
| `FY2027` | financial year twenty twenty seven |
| `Q1` | quarter one |
| `Q1 FY2024-25` | quarter one of financial year twenty twenty four twenty twenty five |

> [!NOTE]
>
> A two-part number like `23/06` is read as a fraction, not a date. Include the year (`23/06/2026`) if you mean a date.

***

## Time

| Format | Example | English output | Notes |
| :- | :- | :- | :- |
| H:MM with AM/PM | `5:30 PM` | five thirty P M | AM/PM is always spelled as letters |
| 24-hour (0, 13–23) | `20:00` | eight P M | Converted to natural 12-hour with AM/PM inferred |
| H:MM, no AM/PM | `5:30` | five thirty | AM/PM not guessed when ambiguous |
| H:MM:SS | `1:30:45` | one thirty and forty five seconds | |
| H:MM:SS AM/PM | `11:59:59 PM` | eleven fifty nine and fifty nine seconds P M | |
| H:MM–H:MM range | `10:00–11:30 AM` | ten and eleven thirty A M | |
| Bare H AM/PM | `5 PM` | five P M | No colon needed |
| HH:MM hrs | `22:00 hrs` | ten P M | |

Non-English languages use their own natural time phrasing rather than a direct translation of the English pattern.

***

## Math Symbols

| Symbol | Reads as | Example |
| :- | :- | :- |
| `+` | plus | `2 + 3` → two plus three |
| `=` | is equal to | `= 5` → is equal to five |
| `×`, `x`, `*` | multiplied by | `2 x 3` → two multiplied by three |
| `÷` | divided by | `10 ÷ 2` → ten divided by two |
| `√` | square root of | `√64` → square root of sixty four |
| `±` | plus or minus | `5 ± 2` → five plus or minus two |
| `<` / `>` | less than / greater than | `>90` → greater than ninety |
| `≤` / `≥` | less than or equal to / greater than or equal to | `≥10` → greater than or equal to ten |
| `²` / `³` | squared / cubed | `5²` → five squared |
| `½` `¼` `¾` | and a half / and a quarter / and three quarters | `2½` → two and a half |

> [!NOTE]
>
> When `×`, `x`, or `*` is immediately followed by a unit (`inches`, `cm`, `ft`), it reads as "by" instead of "multiplied by" — `5x7 inches` → "five by seven inches." The fixed idiom `24x7`, `24×7`, and `24/7` always reads as "twenty four seven."

***

## Fractions

A bare `<number>/<number>` that isn't part of a recognized date reads as a fraction:

| Input | English | Hindi | Marathi |
| :- | :- | :- | :- |
| `1/2` | one by two | एक बटा दो | एक भागिले दोन |
| `23/06` | twenty three by six | — | — |

Only Hindi and Marathi have a confirmed native connector word ("बटा" / "भागिले"). The other seven languages use the English loanword "by."

***

## Units & Measurements

| Unit | Reads as | Notes |
| :- | :- | :- |
| `kg` | kilograms | any case |
| `g` | grams | lowercase only — uppercase `G` after a digit is the 4G/5G telecom pattern |
| `km` | kilometres | any case |
| `mg` | milligrams | lowercase only — avoids misreading "123 MG Road" as a dosage |
| `mcg` | micrograms | any case |
| `ml` / `mL` | millilitres | any case |
| `L` | litres | any case |
| `m` | metres | any case |
| `ms` | milliseconds | any case |
| `°C` / `°F` | degrees Celsius / degrees Fahrenheit | |
| `kcal` | kilocalories | any case |
| `GB` / `MB` / `TB` | gigabytes / megabytes / terabytes | any case |
| `Mbps` / `MBps` | megabits/megabytes per second | **exact case only** — any other casing is left unexpanded |
| `Kbps` | kilobits per second | any case |
| `km/h` / `kmph` | kilometres per hour | any case |
| `sqft` | square feet | any case |

| Notation | Reads as | Example |
| :- | :- | :- |
| `5'11''` or `5'11"` | feet + inches | five feet eleven inches |
| `12°N, 77°E` | degrees + compass direction | twelve degrees North, seventy seven degrees East |
| `₹4,500/month` | per + period | …rupees per month |
| `₹599/28 days` | per + count + period | …rupees per twenty eight days |

> [!WARNING]
>
> A bare `5°` with no unit letter (`C`/`F`) or compass direction (`N`/`S`/`E`/`W`) is not normalized. Always include the unit so temperatures and coordinates read correctly.

***

## Roman Numerals

Roman numerals are only converted in two cases:

1. The entire input is a roman numeral by itself (`XIV` → fourteen).
2. A roman numeral immediately follows a trigger word: `Chapter`, `Part`, `Section`, `Volume`, `Book`, `Class`, `Grade`, `King`, `Queen`, `Pope`, `Emperor`, `World War`, `Super Bowl`, `Article`, or `Appendix` (e.g. "Chapter XIV" → "Chapter fourteenth").

Ordinary words that happen to look like roman numerals (`MIX`, `CIVIC`, `MD`) are never converted in normal sentences.

***

## Identifiers

Structured IDs are read with grouped digits/letters and natural pauses between groups.

| Entity | Example input | Readout pattern |
| :- | :- | :- |
| PAN | `ABCDE1234F` | Letters, then digits, then final letter — each group set off by a pause. Read as the word "pan" (not "P A N") |
| Aadhaar | `1234-5678-9012` | Three groups of 4 digits, separated by pauses |
| IFSC | `SBIN0001234` | Bank code as one spoken group, then branch code spelled out |
| GST / GSTIN | `GST 22ABCDE1234F1Z5` | "G S T" followed by the full code character-by-character |
| Phone (10-digit) | `9876543210` | Grouped 3-3-4, comma-separated |
| Phone (international) | `+91 98765 43210` | "plus" + country code, then the national number |
| Toll-free / landline | `1800-440-1234` | Read in the written digit groups |
| OTP | `OTP is 482913` | Digits spelled individually |
| PIN | `ATM PIN: 1234` | Digit-by-digit |
| Masked number | `****4821` | Mask skipped, only visible digits read |
| Account / reference code | `account ABC1234` | Trigger word + code spelled in groups |
| Vehicle plate | `DL 1C AF 5031` | Full plate spelled character-by-character |
| Train / flight number | `flight AI 101` | Trigger word + code spelled out |
| EPIC (voter ID) | `EPIC/WB/8821` | Each segment spelled out, joined by "slash" |
| Seat / gate / row | `Seat 15A`, `Gate 14B` | "fifteen A", "fourteen B" |
| Invoice / order # | `#12345`, `Invoice #12345` | "Invoice number one two three four five" |
| UPI handle | `9876543210@ybl` | Digit local part spelled in chunks; bank suffix spelled letter-by-letter |

> [!WARNING]
>
> **Known identifier limitations:**
>
> * **4-segment EPIC IDs** (e.g. `EPIC/WB/8821/4521`) can misread — a fraction rule may claim the last two segments. Use the 3-segment form or a non-slash separator until fixed.
> * **OTP/PIN digits** may be read with "double/triple" compression for repeated digits (e.g. `448822` → "double four double eight double two"). Contact your Gnani representative if you need guaranteed uncompressed digit-by-digit OTP readout.
> * **Very long reference numbers** (14+ digits) are read as a raw digit string rather than being grouped. Add your own separators (spaces or hyphens) for a more natural readout.

***

## URLs, Emails & UPI Handles

| Input | Output |
| :- | :- |
| `https://abc123.com/path1` | H T T P S colon slash slash abc one two three dot com slash path one |
| `www.gov.in/schemes` | W W W dot gov dot in slash schemes |
| `ram.kumar99@hdfc.co.in` | Local part spelled in chunks, domain read dot-by-dot |

URLs and emails are always read in English regardless of the target language. Digits inside them use English digit words even in non-English speech.

***

## Honorifics

| Written | English | Hindi |
| :- | :- | :- |
| `Mr.` | Mister | श्री |
| `Mrs.` | Missus | श्रीमती |
| `Ms.` | Miss | सुश्री |
| `Dr.` | Doctor | डॉक्टर |
| `Prof.` | Professor | प्रोफ़ेसर |
| `Shri` / `Sh.` | Shri | श्री |
| `Shrimati` / `Smt.` | Shrimati | श्रीमती |
| `Kumari` / `Km.` | Kumari | कुमारी |

Every supported language has its own honorific table (e.g. Tamil `Mr.` → திரு, Telugu `Dr.` → డాక్టర్).

> [!NOTE]
>
> `Km.` and `Ms.` also look like unit abbreviations (kilometres, milliseconds). When a number directly precedes them (`10 km`, `200 ms`), they read as the unit, not the honorific. This is a deliberate trade-off — real-world text essentially never has a number immediately before a name.

***

## Address & Business Abbreviations

These are always read in English, since they're conventionally spoken as English loanwords even in Indic-language speech.

| Written | Reads as | Notes |
| :- | :- | :- |
| `St` / `St.` before a comma | Street | `123 Main St, Delhi` → "Main Street, Delhi" |
| `St` / `St.` before a capitalized word | Saint | `St. Xavier's` → "Saint Xavier's" |
| `Rd` | Road | |
| `Ave` | Avenue | |
| `Ln` | Lane | |
| `Blvd` | Boulevard | |
| `Apt` | Apartment | |
| `Bldg` | Building | |
| `Sec` | Sector | |
| `Dist` | District | |
| `Opp` | Opposite | |
| `Nr` | Near | |
| `Pvt` | Private | |
| `Ltd` | Limited | |
| `Co.` | Company | Only with a trailing period — "Co-founder" is untouched |
| `Inc` | Incorporated | |
| `Corp` | Corporation | |
| `No.` before digits | Number | Only when directly followed by digits |
| `(Gen)` | General | Parenthetical form only — "Gen Z" is untouched |

***

## Brand & Product Name Pronunciation

Some brand names don't have a reliable pronunciation from their spelling. As an example, Gnani is rendered natively per language rather than read literally:

| Language | Pronunciation |
| :- | :- |
| English | Gyaanee |
| Hindi / Marathi | ज्ञानी |
| Kannada | ಜ್ಞಾನಿ |
| Telugu | జ్ఞాని |
| Malayalam | ജ്ഞാനി |
| Tamil | ஞானி |
| Gujarati | જ્ઞાની |
| Punjabi | ਗਿਆਨੀ |
| Bengali | জ্ঞানী |

This only applies to the standalone word — "Gnani" inside an email address is read as a normal email, not substituted.

If a brand or product name in your content consistently misreads, contact your Gnani point of contact — custom pronunciation entries can be added.

***

## Common Abbreviations

These initialisms are always spelled letter-by-letter:

> [accordion] Full list of letter-by-letter abbreviations
>
> OTP, EMI, UPI, NEFT, RTGS, NACH, IMPS, ATM, KYC, GST, GSTIN, IFSC, SMS, IVR, API, URL, AI, ML, GPU, CPU, VPN, HTML, CSS, XML, OCR, QR, SDK, GB, MB, TB, CV, FY, MD, SBI, FD, PDF, IIT, IIM, NIT, HDFC, ICICI, NRI, JEE, NEET, OTT, GDP, FIR, TAN, TIN, DIN, COO, USB, LED, LCD, TV, DNA, CVV, UAN, EPF, NGO, CEO, CFO, CTO, AIIMS, UPSC, IAS, IPS, RTO, PPF, NPS, DTH, NOC, HSN

A smaller set is read as a word instead of being spelled out: `PIN`, `SIM`, `RAM`, `ROM`, `AIDS`, `SEBI`, `TRAI`, `CIBIL`, `RERA`, `AMFI`. `Govt` expands to "Government." `Aadhaar` is always kept as-is.

Devanagari-spelled Latin abbreviations are recognized the same way — e.g. `केवाईसी` expands to "के वाई सी" (KYC).

***

## Telecom Generation

| Input | Output |
| :- | :- |
| `5G` | five G |
| `4G` | four G |

Scoped to 2G–5G so it's never misread as a measurement (e.g. "five grams").

***

## Duration Phrases

| Input | Output |
| :- | :- |
| `15 minutes` | fifteen minutes |
| `2 hours` | two hours |
| `3 days` | three days |

Abbreviated units expand to their full word (`hrs` → "hours", `min` → "minutes", `sec` → "seconds"). Numbers near a duration word are always read as a quantity, even if they'd otherwise look like an ID.

> [!NOTE]
>
> The singular `hr` (e.g. "1 hr later") is **not** covered — `HR` is reserved for "Human Resources." Use the full word `hour` or the plural `hrs` for duration.

***

## Natural Pauses

Beyond punctuation already in your text, pause commas are automatically inserted for dense identifier patterns — PAN numbers, Aadhaar, OTPs near long digit runs, IFSC near a bank code, or international phone numbers with `+91`. This prevents multiple codes from running together.

Outside these specific patterns, extra commas are not added. Simpler sentences also have excess commas trimmed so the readout doesn't sound choppy.

***

## Known Limitations

| Limitation | Workaround |
| :- | :- |
| Two-part dates like `23/06` read as a fraction | Include the year: `23/06/2026` |
| `5°` with no unit letter isn't normalized | Write `5°C`, `5°F`, or a compass direction |
| 4-segment EPIC IDs can misread | Use the 3-segment form or a non-slash separator |
| Very long reference numbers (14+ digits) read as raw digit strings | Add spaces or hyphens between groups |
| Singular `hr` reads as "H R", not "hour" | Use `hour` or `hrs` |
| `minus` is not localized — every language uses the English word | No workaround yet |
| Repeated OTP/PIN digits may be compressed ("double four" instead of "four four") | Contact your Gnani representative if strict digit-by-digit readout is required |
| `Mbps`/`MBps` are only guaranteed correct in their exact documented casing | Use the exact case shown; other casings are left unexpanded |
| `auto` detection with Latin-script-only input always resolves to English | Pass the language hint explicitly (e.g. `"kn"`) |
| Fraction connector word "by" only has a native form in Hindi and Marathi | Other languages use the English loanword |


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.