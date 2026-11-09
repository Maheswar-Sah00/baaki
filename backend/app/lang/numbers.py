"""Indian-rupee numbers: formatting, spelling out for TTS read-back, parsing.

Deterministic on purpose: the LLM never produces an amount. Everything that
turns speech-to-text output into a rupee value goes through ``compose`` below,
and everything we read back goes through ``inr_to_words``.

Public API
----------
format_inr(amount) -> "₹1,20,000"
number_to_words(n, lang) -> words without the currency word
inr_to_words(amount, lang) -> words with the currency word, lang in te|hi|hinglish|en
words_to_number(text, lang=None) -> int | None   (first exact number phrase)
te_words_to_number / te_roman_words_to_number / hi_words_to_number /
hinglish_words_to_number / en_words_to_number -> per-language wrappers

Range: 0 .. 99,99,99,999 (999,999,999), whole rupees only.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

from ._text import Tok, key_for, norm_deva, norm_telu, skel, tokenize, work_text

MAX_INR = 999_999_999  # 99,99,99,999
LAKH = 100_000
CRORE = 10_000_000

# ===========================================================================
# 1. Canonical spellings used for read-back (output side)
# ===========================================================================

# --- Telugu (as spoken colloquially in Hyderabad) ---------------------------
TE_UNITS = [
    "సున్నా",  # 0
    "ఒకటి",  # 1  (attributive "ఒక", "ఒక్క" before a noun / in compounds)
    "రెండు",  # 2
    "మూడు",  # 3
    "నాలుగు",  # 4
    "ఐదు",  # 5  (alt. spelling అయిదు)
    "ఆరు",  # 6
    "ఏడు",  # 7
    "ఎనిమిది",  # 8
    "తొమ్మిది",  # 9
    "పది",  # 10
    "పదకొండు",  # 11
    "పన్నెండు",  # 12
    "పదమూడు",  # 13
    "పద్నాలుగు",  # 14
    "పదిహేను",  # 15
    "పదహారు",  # 16
    "పదిహేడు",  # 17
    "పద్దెనిమిది",  # 18
    "పందొమ్మిది",  # 19
]
TE_TENS = {
    20: "ఇరవై",
    30: "ముప్పై",  # alt. ముప్ఫై
    40: "నలభై",  # alt. నలబై
    50: "యాభై",  # alt. యాబై, ఏభై
    60: "అరవై",
    70: "డెబ్బై",
    80: "ఎనభై",  # alt. ఎనబై
    90: "తొంభై",  # alt. తొంబై
}
TE_ONE_ATTR = "ఒక"  # ఒక లక్ష, ఒక కోటి, ఒక రూపాయి
TE_ONE_COMPOUND = "ఒక్క"  # ఇరవై ఒక్క వేలు, నూట ఒక్క రూపాయలు (alt. ఇరవై ఒక)
TE_HUNDRED = "వంద"  # exactly 100 (alt. నూరు)
TE_HUNDRED_PREFIX = "నూట"  # 1xx: నూట యాభై = 150
TE_HUNDREDS, TE_HUNDREDS_OBL = "వందలు", "వందల"  # రెండు వందలు / రెండు వందల యాభై
TE_THOUSAND = "వెయ్యి"  # 1000 (alt. వేయి)
TE_THOUSANDS, TE_THOUSANDS_OBL = "వేలు", "వేల"  # రెండు వేలు / రెండు వేల రూపాయలు
TE_LAKH = "లక్ష"  # colloquial alt. "లక్షా ఇరవై వేలు"
TE_LAKHS, TE_LAKHS_OBL = "లక్షలు", "లక్షల"
TE_CRORE = "కోటి"
TE_CRORES, TE_CRORES_OBL = "కోట్లు", "కోట్ల"
TE_RUPEES, TE_RUPEE = "రూపాయలు", "రూపాయి"
TE_AND = "మరియు"  # only used for 1,00,020-style amounts, see _needs_and()

# --- Hindi, Devanagari. 1-99 are irregular, so the full table. -------------
HI_1_99 = [
    "शून्य", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ",
    "दस", "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह", "अठारह", "उन्नीस",
    "बीस", "इक्कीस", "बाईस", "तेईस", "चौबीस", "पच्चीस", "छब्बीस", "सत्ताईस", "अट्ठाईस", "उनतीस",
    "तीस", "इकतीस", "बत्तीस", "तैंतीस", "चौंतीस", "पैंतीस", "छत्तीस", "सैंतीस", "अड़तीस", "उनतालीस",
    "चालीस", "इकतालीस", "बयालीस", "तैंतालीस", "चवालीस", "पैंतालीस", "छियालीस", "सैंतालीस", "अड़तालीस", "उनचास",
    "पचास", "इक्यावन", "बावन", "तिरपन", "चौवन", "पचपन", "छप्पन", "सत्तावन", "अट्ठावन", "उनसठ",
    "साठ", "इकसठ", "बासठ", "तिरसठ", "चौंसठ", "पैंसठ", "छियासठ", "सड़सठ", "अड़सठ", "उनहत्तर",
    "सत्तर", "इकहत्तर", "बहत्तर", "तिहत्तर", "चौहत्तर", "पचहत्तर", "छिहत्तर", "सतहत्तर", "अठहत्तर", "उन्यासी",
    "अस्सी", "इक्यासी", "बयासी", "तिरासी", "चौरासी", "पचासी", "छियासी", "सत्तासी", "अट्ठासी", "नवासी",
    "नब्बे", "इक्यानवे", "बानवे", "तिरानवे", "चौरानवे", "पचानवे", "छियानवे", "सत्तानवे", "अट्ठानवे", "निन्यानवे",
]
HI_HUNDRED, HI_THOUSAND, HI_LAKH, HI_CRORE = "सौ", "हज़ार", "लाख", "करोड़"
HI_RUPEES, HI_RUPEE = "रुपये", "रुपया"

# --- Hinglish (Latin) ------------------------------------------------------
HINGLISH_1_99 = [
    "zero", "ek", "do", "teen", "chaar", "paanch", "chhah", "saat", "aath", "nau",
    "das", "gyaarah", "baarah", "terah", "chaudah", "pandrah", "solah", "satrah", "athaarah", "unnees",
    "bees", "ikkees", "baaees", "teis", "chaubees", "pachchees", "chhabbees", "sattaaees", "atthaaees", "untees",
    "tees", "ikattees", "battees", "taintees", "chauntees", "paintees", "chhattees", "saintees", "adtees", "untaalees",
    "chaalees", "iktaalees", "bayaalees", "taintaalees", "chavaalees", "paintaalees", "chhiyaalees", "saintaalees", "adtaalees", "unchaas",
    "pachaas", "ikyaavan", "baavan", "tirpan", "chauvan", "pachpan", "chhappan", "sattaavan", "atthaavan", "unsath",
    "saath", "iksath", "baasath", "tirsath", "chaunsath", "painsath", "chhiyaasath", "sadsath", "adsath", "unhattar",
    "sattar", "ikhattar", "bahattar", "tihattar", "chauhattar", "pachhattar", "chhihattar", "satattar", "athhattar", "unaasi",
    "assi", "ikyaasi", "bayaasi", "tiraasi", "chauraasi", "pachaasi", "chhiyaasi", "sattaasi", "atthaasi", "navaasi",
    "nabbe", "ikyaanve", "baanve", "tiraanve", "chauraanve", "pachaanve", "chhiyaanve", "sattaanve", "atthaanve", "ninyaanve",
]
HG_HUNDRED, HG_THOUSAND, HG_LAKH, HG_CRORE = "sau", "hazaar", "lakh", "crore"
HG_RUPEES, HG_RUPEE = "rupaye", "rupaya"

# --- English (Indian system) ----------------------------------------------
EN_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
]
EN_TENS = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"}


# ===========================================================================
# 2. Parsing lexicons (input side)
# ===========================================================================
@dataclass(frozen=True)
class Lex:
    kind: str  # num | mult | frac | adj | cur | conn | range
    value: Fraction | None = None
    tens: bool = False  # 20, 30 ... 90 as a word: may take a unit after it
    needs_coef: bool = False  # plural multiplier (వేలు, lakhs): needs a number before it
    half: bool = False  # లక్షన్నర: coefficient + 1/2
    ambiguous: bool = False  # also a common non-number word (do, saath, teen ...)


def _num(v, tens=False, ambiguous=False) -> tuple[Lex, ...]:
    return (Lex("num", Fraction(v), tens=tens, ambiguous=ambiguous),)


def _mult(v, needs_coef=False) -> tuple[Lex, ...]:
    return (Lex("mult", Fraction(v), needs_coef=needs_coef),)


def _frac(v, ambiguous=False) -> tuple[Lex, ...]:
    return (Lex("frac", Fraction(v), ambiguous=ambiguous),)


def _adj(v) -> tuple[Lex, ...]:
    return (Lex("adj", Fraction(v)),)


CUR = (Lex("cur"),)
CONN = (Lex("conn"),)
RANGE = (Lex("range"),)


class _LexTable(dict):
    """dict that refuses two different meanings for the same key."""

    def __init__(self, name: str, keyfn):
        super().__init__()
        self.name = name
        self.keyfn = keyfn

    def put(self, words, entry):
        if isinstance(words, str):
            words = [words]
        for w in words:
            k = self.keyfn(w)
            old = self.get(k)
            if old is not None and old != entry:
                raise ValueError(f"{self.name}: '{w}' (key {k!r}) maps to {old} and {entry}")
            self[k] = entry


# --- Telugu script ---------------------------------------------------------
TE_LEX = _LexTable("te", norm_telu)
_TE_NUM_VARIANTS = {
    1: [TE_ONE_ATTR, TE_ONE_COMPOUND, "ఒక్కటి"],
    5: ["అయిదు"],
    14: ["పధ్నాలుగు"],
    15: ["పదైదు"],
    16: ["పదారు"],
    18: ["పద్ధెనిమిది"],
    19: ["పంతొమ్మిది"],
}
_TE_TENS_VARIANTS = {
    20: ["ఇరువై", "ఇరవయి"],
    30: ["ముప్ఫై", "ముప్పయి", "ముప్పది"],
    40: ["నలబై", "నలభయి", "నలుబది"],
    50: ["యాబై", "ఏభై", "యాభయి", "ఏబది"],
    60: ["అరవయి", "అరువది"],
    70: ["డెబ్బయి", "డెబ్బది"],
    80: ["ఎనబై", "ఎనభయి", "ఎనుబది"],
    90: ["తొంబై", "తొంభయి", "తొంబది"],
}
for _v, _w in enumerate(TE_UNITS):
    TE_LEX.put([_w] + _TE_NUM_VARIANTS.get(_v, []), _num(_v))
for _v, _w in TE_TENS.items():
    TE_LEX.put([_w] + _TE_TENS_VARIANTS.get(_v, []), _num(_v, tens=True))

# Sandhi compounds: ఇరవై + ఐదు -> ఇరవయ్యైదు, యాభై + ఒకటి -> యాభయ్యొకటి.
_TE_VOWEL_SIGN = {"ఒ": "ొ", "ఐ": "ై", "ఆ": "ా", "ఏ": "ే", "ఎ": "ె"}
for _tv, _tw in TE_TENS.items():
    for _tword in [_tw] + _TE_TENS_VARIANTS.get(_tv, []):
        for _u in range(1, 10):
            _uwords = [TE_UNITS[_u]] + _TE_NUM_VARIANTS.get(_u, []) if _u != 1 else [TE_UNITS[1], TE_ONE_COMPOUND]
            for _uw in _uwords:
                entry = (Lex("num", Fraction(_tv), tens=True), Lex("num", Fraction(_u)))
                TE_LEX.put(_tword + _uw, entry)  # glued: ఇరవైరెండు
                if _tword.endswith("ై") and _uw[0] in _TE_VOWEL_SIGN:
                    TE_LEX.put(_tword[:-1] + "య్య" + _TE_VOWEL_SIGN[_uw[0]] + _uw[1:], entry)

TE_LEX.put([TE_HUNDRED, "నూరు", TE_HUNDRED_PREFIX, "వందా", "హండ్రెడ్"], _mult(100))
TE_LEX.put([TE_HUNDREDS, TE_HUNDREDS_OBL], _mult(100, needs_coef=True))
TE_LEX.put([TE_THOUSAND, "వేయి", "వెయ్యీ", "థౌజండ్", "థౌసండ్"], _mult(1000))
TE_LEX.put([TE_THOUSANDS, TE_THOUSANDS_OBL], _mult(1000, needs_coef=True))
TE_LEX.put([TE_LAKH, "లక్షా"], _mult(LAKH))
TE_LEX.put([TE_LAKHS, TE_LAKHS_OBL], _mult(LAKH, needs_coef=True))
TE_LEX.put([TE_CRORE, "కోటీ"], _mult(CRORE))
TE_LEX.put([TE_CRORES, TE_CRORES_OBL], _mult(CRORE, needs_coef=True))
TE_LEX.put("అర", _frac(Fraction(1, 2)))  # అర లక్ష = 50,000
TE_LEX.put("పావు", _frac(Fraction(1, 4)))  # పావు లక్ష = 25,000
TE_LEX.put("ముప్పావు", _frac(Fraction(3, 4)))
TE_LEX.put([TE_RUPEES, "రూపాయల", TE_RUPEE, "రూపాయిలు", "రూపాయిల", "రూపాయీ", "రూ"], CUR)
TE_LEX.put(["లేదా", "నుంచి", "నుండి"], RANGE)
TE_LEX.put(["మరియు"], CONN)
# Colloquial contraction: రెండొందలు (200), ఐదొందల (500 ...), తొమ్మిదొందలు (900)
for _v in range(2, 10):
    _w = TE_UNITS[_v]
    if _w[-1] in "ుి":  # ends in ు or ి
        for _suf in ("ొందలు", "ొందల"):
            TE_LEX.put(_w[:-1] + _suf, (Lex("num", Fraction(_v)), Lex("mult", Fraction(100))))

_TE_SUFFIXES = sorted(
    ["కి", "కు", "కీ", "లో", "్లో", "ని", "ను", "తో", "గా", "కే", "దాకా", "వరకు", "నుంచి",
     "నుండి", "లోపు", "లోగా", "కల్లా", "ే", "ా"],
    key=len, reverse=True,
)
_TE_MULT_FORMS = sorted(
    [k for k, v in TE_LEX.items() if len(v) == 1 and v[0].kind in ("mult", "cur")], key=len, reverse=True
)


@lru_cache(maxsize=65536)
def _lookup_te(word: str, depth: int = 0) -> tuple[Lex, ...] | None:
    k = norm_telu(word)
    hit = TE_LEX.get(k)
    if hit is not None:
        return hit
    # రెండున్నర = 2.5, లక్షన్నర = 1.5 lakh, వెయ్యిన్నర = 1500
    if k.endswith("న్నర") and len(k) > 4:
        base = TE_LEX.get(k[:-4])
        if base and len(base) == 1:
            b = base[0]
            if b.kind == "num":
                return (Lex("num", b.value + Fraction(1, 2)),)
            if b.kind == "mult":
                return (Lex("mult", b.value, half=True),)
    if depth == 0:
        for suf in _TE_SUFFIXES:
            if k.endswith(suf) and len(k) > len(suf):
                hit = _lookup_te(k[: -len(suf)], depth=1)
                if hit is not None:
                    return hit
        # glued number + multiplier: పదివేలు, యాభైవేల
        for m in _TE_MULT_FORMS:
            if k.endswith(m) and len(k) > len(m):
                pre = TE_LEX.get(k[: -len(m)])
                if pre and all(x.kind == "num" for x in pre):
                    return pre + TE_LEX[m]
    return None


# --- Hindi, Devanagari -----------------------------------------------------
HI_LEX = _LexTable("hi", norm_deva)
_HI_VARIANTS = {
    5: ["पांच"], 6: ["छः", "छे", "छै", "छ"], 15: ["पन्द्रह"], 17: ["सतरह"], 18: ["अट्ठारह"],
    22: ["बाइस"], 23: ["तेइस"], 27: ["सत्ताइस"], 28: ["अट्ठाइस", "अठाईस", "अठ्ठाईस"], 29: ["उन्तीस"],
    33: ["तेंतीस", "तैतीस"], 34: ["चौतीस"], 35: ["पैतीस", "पेंतीस"], 37: ["सेंतीस", "सैतीस"],
    39: ["उन्तालीस"], 43: ["तेंतालीस", "तैतालीस"], 44: ["चौवालीस", "चौंवालीस", "चव्वालीस"],
    45: ["पैतालीस", "पेंतालीस"], 46: ["छयालीस"], 47: ["सेंतालीस", "सैतालीस"], 49: ["उन्चास"],
    51: ["इकावन", "इक्कावन"], 53: ["तिरेपन"], 54: ["चव्वन"], 58: ["अठावन"], 59: ["उन्सठ"],
    63: ["तिरेसठ"], 64: ["चौसठ"], 65: ["पैसठ"], 66: ["छाछठ"], 67: ["सरसठ"], 68: ["अरसठ"],
    69: ["उन्हत्तर"], 76: ["छियत्तर"], 77: ["सत्तत्तर"], 78: ["अठत्तर"], 79: ["उनासी", "उनयासी"],
    81: ["इकयासी"], 82: ["बियासी"], 88: ["अठासी"], 91: ["इक्यानबे"], 92: ["बानबे"], 93: ["तिरानबे"],
    94: ["चौरानबे"], 95: ["पंचानवे", "पचानबे"], 96: ["छियानबे"], 97: ["सत्तानबे"], 98: ["अट्ठानबे", "अठानवे"],
    99: ["निन्यानबे", "निन्नानवे"],
}
for _v, _w in enumerate(HI_1_99):
    # Hindi has a word for every number 1-99, so a tens word never takes a unit
    # after it: "bees paanch" / "bees pachees" is a range, not 25 or 45.
    HI_LEX.put([_w] + _HI_VARIANTS.get(_v, []), _num(_v))
HI_LEX.put([HI_HUNDRED, "हंड्रेड"], _mult(100))
HI_LEX.put([HI_THOUSAND, "थाउजेंड", "थाउसेंड"], _mult(1000))
HI_LEX.put(HI_LAKH, _mult(LAKH))
HI_LEX.put(HI_CRORE, _mult(CRORE))
HI_LEX.put("डेढ़", _frac(Fraction(3, 2)))
HI_LEX.put(["ढाई", "अढ़ाई"], _frac(Fraction(5, 2)))
HI_LEX.put(["आधा", "आधे", "आधी"], _frac(Fraction(1, 2)))
HI_LEX.put("सवा", _adj(Fraction(1, 4)))
HI_LEX.put("साढ़े", _adj(Fraction(1, 2)))
HI_LEX.put("पौने", _adj(Fraction(-1, 4)))
HI_LEX.put([HI_RUPEES, "रुपए", HI_RUPEE, "रूपये", "रूपए", "रूपया", "रुपयों", "रुपैया", "रु", "रू"], CUR)
HI_LEX.put("और", CONN)
HI_LEX.put(["या", "से"], RANGE)

# --- Latin lexicons (keys are spelling skeletons) --------------------------
EN_LEX = _LexTable("en", skel)
for _v, _w in enumerate(EN_ONES):
    EN_LEX.put(_w, _num(_v))
for _v, _w in EN_TENS.items():
    EN_LEX.put(_w, _num(_v, tens=True))
EN_LEX.put("fourty", _num(40, tens=True))
EN_LEX.put("hundred", _mult(100))
EN_LEX.put("hundreds", _mult(100, needs_coef=True))
EN_LEX.put("thousand", _mult(1000))
EN_LEX.put("thousands", _mult(1000, needs_coef=True))
EN_LEX.put(["lakh", "lac", "laakh"], _mult(LAKH))
EN_LEX.put(["lakhs", "lacs", "laks"], _mult(LAKH, needs_coef=True))
EN_LEX.put(["million"], _mult(1_000_000))
EN_LEX.put(["millions"], _mult(1_000_000, needs_coef=True))
EN_LEX.put(["crore", "cr", "karod", "karor"], _mult(CRORE))
EN_LEX.put(["crores", "crs"], _mult(CRORE, needs_coef=True))
EN_LEX.put("half", _frac(Fraction(1, 2)))
EN_LEX.put("quarter", _frac(Fraction(1, 4)))
EN_LEX.put(["rupees", "rupee", "rs", "inr", "bucks"], CUR)
EN_LEX.put("and", CONN)
EN_LEX.put(["or", "to"], RANGE)

HG_LEX = _LexTable("hinglish", skel)
_HG_VARIANTS = {
    0: ["shunya", "shoonya", "sunya"],
    1: ["ekk", "aik"], 2: [], 3: ["tin", "theen"], 4: ["char", "chār"],
    5: ["panch", "paanc", "paach", "panc"], 6: ["chhe", "che", "chah", "chheh", "chhai", "chhey", "cheh", "chha"],
    7: ["sat"], 8: ["aat", "ath"], 9: ["nao"], 10: ["dus", "dass"],
    11: ["gyarah", "gyara", "gyaara", "gyarha", "giyarah"], 12: ["barah", "bara", "baara", "barha"],
    13: ["tera", "tehra", "terha"], 14: ["chauda", "choudah", "chouda", "chaudha", "chodah"],
    15: ["pandra", "pandhra", "pandara", "pundrah", "pandrha"], 16: ["sola", "solha"],
    17: ["satra", "sattrah", "satarah", "satara"],
    18: ["atharah", "athara", "attharah", "atthara", "athaara", "atharaa"],
    19: ["unnis", "unees", "unis"], 20: ["bis"], 21: ["ikkis", "ikis", "ikees"],
    22: ["bais", "baais", "baees", "bayees"], 23: ["teyis", "tei", "teees"],
    24: ["chaubis", "choubees", "choubis", "chobis"],
    25: ["pachees", "pachis", "pachchis", "pacchis", "pacchees"],
    26: ["chabbees", "chhabbis", "chabbis"], 27: ["sattais", "sataees", "sattayis", "sataais"],
    28: ["atthais", "athais", "athaees", "atthayis", "athayis"], 29: ["untis", "unatis", "unattis"],
    30: ["tis"], 31: ["ikattis", "iktees", "iktis", "ikatis"], 32: ["battis", "batis"],
    33: ["taintis", "tetees", "tetis", "taitees", "taitis", "tentis"],
    34: ["chauntis", "chautees", "chautis", "chontis"], 35: ["paintis", "paitees", "paitis", "pentis"],
    36: ["chhattis", "chattees", "chattis", "chatis"], 37: ["saintis", "saitees", "saitis", "sentis"],
    38: ["adtis", "artees", "artis", "adhtis"], 39: ["untalis", "untaalis", "unthalis"],
    40: ["chalis", "chaalis", "chalees"], 41: ["iktalis", "iktaalis"],
    42: ["bayalis", "byalis", "byaalis", "bayalees"], 43: ["taintalis", "tentalis", "taitalis", "taitaalees"],
    44: ["chavalis", "chawalis", "chauvalis", "chauwalis", "chavvalis"],
    45: ["paintalis", "pentalis", "paitalis"], 46: ["chhiyalis", "chiyalis", "chhayalis"],
    47: ["saintalis", "sentalis", "saitalis"], 48: ["adtalis", "artalis", "artaalis"],
    49: ["unchas"], 50: ["pachas"], 51: ["ikyavan", "ikyawan", "ikkyavan", "ikavan"],
    52: ["bavan", "bawan", "baawan"], 53: ["tirepan", "tirapan", "trepan"],
    54: ["chauwan", "chouvan", "chowan", "chauvvan"], 55: ["pachapan", "pachpun"],
    56: ["chappan", "chhapan"], 57: ["sattavan", "sattawan", "satavan"],
    58: ["atthavan", "athavan", "athawan", "atthawan"], 59: ["unsaath", "unsat"],
    60: ["sath"], 61: ["iksaath", "iksat"], 62: ["basath", "baasat"], 63: ["tirsaath", "tiresath"],
    64: ["chausath", "chonsath", "chaunsaath"], 65: ["paisath", "pensath", "painsaath"],
    66: ["chhiyasath", "chiyasath"], 67: ["sarsath", "sadsaath"], 68: ["arsath", "adsaath"],
    69: ["unahattar", "unhatar"], 71: ["ikahattar"], 72: ["bahatar"], 73: ["tehattar"],
    74: ["chohattar"], 75: ["pachattar", "pachahattar"], 76: ["chihattar", "chhiyattar"],
    77: ["satahattar", "sathattar"], 78: ["athattar", "athahattar"],
    79: ["unasi", "unyaasi", "unyasi"], 80: ["asi"], 81: ["ikyasi", "ikkyasi"],
    82: ["bayasi", "byasi", "biyasi"], 83: ["tirasi"], 84: ["chaurasi", "chorasi"], 85: ["pachasi"],
    86: ["chhiyasi", "chiyasi"], 87: ["sattasi", "satasi"], 88: ["atthasi", "athasi"],
    89: ["navasi", "nawasi"], 90: ["nabbay", "nabe"], 91: ["ikyanve", "ikyanave", "ikyaanave"],
    92: ["banve", "banave"], 93: ["tiranve", "tiranave"], 94: ["chauranve", "choranve"],
    95: ["pachanve", "panchanve"], 96: ["chhiyanve", "chiyanve"], 97: ["sattanve"],
    98: ["atthanve", "athanve"], 99: ["ninyanve", "ninnyanve", "ninanve"],
}
# Words that are also everyday Hindi/English words. They only count as numbers
# when another number word, a currency word or a counter (din, tarikh) follows.
_HG_AMBIGUOUS = {skel(w) for w in ("do", "teen", "sat", "saath", "che", "tera", "bara", "nau", "das")}
for _v, _w in enumerate(HINGLISH_1_99):
    for _x in [_w] + _HG_VARIANTS.get(_v, []):
        HG_LEX.put(_x, _num(_v, ambiguous=(skel(_x) in _HG_AMBIGUOUS)))
HG_LEX.put(["sau"], _mult(100))
HG_LEX.put(["hazaar", "hazar", "hajar", "hajaar", "hazzar", "hazār", "hazara"], _mult(1000))
HG_LEX.put(["lakh", "lac", "laakh"], _mult(LAKH))
HG_LEX.put(["lakhs", "lacs"], _mult(LAKH, needs_coef=True))
HG_LEX.put(["crore", "karod", "karor", "karore"], _mult(CRORE))
HG_LEX.put(["crores"], _mult(CRORE, needs_coef=True))
HG_LEX.put(["dedh", "derh", "dedhh", "deedh"], _frac(Fraction(3, 2)))
HG_LEX.put(["dhai", "dhaai", "adhai", "arhai", "dhaee"], _frac(Fraction(5, 2)))
HG_LEX.put(["aadha", "adha", "aadhe", "adhe", "aadhi"], _frac(Fraction(1, 2)))
HG_LEX.put(["sava", "savaa", "sawa", "sawaa", "swa"], _adj(Fraction(1, 4)))
HG_LEX.put(["sade", "saade", "saadhe", "sadhe", "sarhe", "saarhe"], _adj(Fraction(1, 2)))
HG_LEX.put(["paune", "pone", "pauney"], _adj(Fraction(-1, 4)))
HG_LEX.put(["rupaye", "rupaiye", "rupay", "rupaya", "rupye", "rupiya", "rupiye", "rupaiya", "rupees",
            "rupee", "rs", "inr", "ruppees", "ruppaye"], CUR)
HG_LEX.put(["aur"], CONN)
HG_LEX.put(["ya", "se"], RANGE)

TE_LATN_LEX = _LexTable("te-latn", skel)
_TE_LATN_NUM = {
    0: ["sunna", "sunnaa"],
    1: ["okati", "okkati", "oka", "okka"],
    2: ["rendu", "rend"],
    3: ["moodu", "mudu", "muudu"],
    4: ["naalugu", "nalugu", "nalgu", "naalgu"],
    5: ["aidu", "ayidu", "aidhu", "ayudu"],
    6: ["aaru", "aru"],
    7: ["edu", "eedu", "yedu", "yeedu", "yedhu"],
    8: ["enimidi", "enmidi", "yenimidi", "enimidhi", "enumidi"],
    9: ["tommidi", "thommidi", "tommidhi", "thommidhi"],
    10: ["padi", "padhi"],
    11: ["padakondu", "padhakondu", "padkondu"],
    12: ["pannendu", "pannendhu", "panendu"],
    13: ["padamudu", "padamoodu", "padhamoodu", "padmudu"],
    14: ["padnalugu", "padhnalugu", "padunalugu", "padnaalugu"],
    15: ["padihenu", "padhihenu", "padiheenu", "padhenu"],
    16: ["padaharu", "padhaharu", "padahaaru", "padaaru"],
    17: ["padihedu", "padhihedu", "padiheedu"],
    18: ["paddenimidi", "padhenimidi", "paddhenimidi"],
    19: ["pandommidi", "pandhommidi", "panthommidi"],
    20: ["iravai", "iravay", "iruvai", "iravy", "iravayi"],
    30: ["muppai", "muppay", "mupphai", "muppy", "muppayi"],
    40: ["nalabhai", "nalabai", "nalabay", "nalubhai", "nalabhay"],
    50: ["yabhai", "yabai", "yaabhai", "yaabai", "yabay", "ebhai", "yebhai", "yaabhay"],
    60: ["aravai", "aravay", "aravy", "aruvai"],
    70: ["debbai", "debbay", "debbhai", "debbhay"],
    80: ["enabhai", "enabai", "enabay", "yenabhai", "yenabai"],
    90: ["tombhai", "tombai", "thombhai", "thombai", "tombay", "thombay"],
}
for _v, _ws in _TE_LATN_NUM.items():
    TE_LATN_LEX.put(_ws, _num(_v, tens=(_v >= 20), ambiguous=(_v == 10)))
TE_LATN_LEX.put(["vanda", "vandha", "nooru", "nuru", "noota", "nuta", "nuuta"], _mult(100))
TE_LATN_LEX.put(["vandalu", "vandala", "vandhalu", "vandhala"], _mult(100, needs_coef=True))
TE_LATN_LEX.put(["veyyi", "veyi", "vayyi", "veiyi", "veeyi"], _mult(1000))
TE_LATN_LEX.put(["velu", "vela", "veelu", "veela"], _mult(1000, needs_coef=True))
TE_LATN_LEX.put(["laksha", "lakshaa"], _mult(LAKH))
TE_LATN_LEX.put(["lakshalu", "lakshala"], _mult(LAKH, needs_coef=True))
TE_LATN_LEX.put(["koti", "kotee"], _mult(CRORE))
TE_LATN_LEX.put(["kotlu", "kotla"], _mult(CRORE, needs_coef=True))
TE_LATN_LEX.put(["ara"], _frac(Fraction(1, 2), ambiguous=True))
TE_LATN_LEX.put(["paavu", "pavu"], _frac(Fraction(1, 4)))
TE_LATN_LEX.put(["muppavu", "muppaavu"], _frac(Fraction(3, 4)))
TE_LATN_LEX.put(["rupayalu", "rupaayalu", "roopayalu", "rupailu", "rupayilu", "rupayi", "rupaayi",
                 "rupai", "rupayala", "rupaayala"], CUR)
TE_LATN_LEX.put(["leda", "ledha", "nunchi", "nundi"], RANGE)
TE_LATN_LEX.put(["mariyu"], CONN)

LATIN_LEXICONS = {"en": EN_LEX, "hinglish": HG_LEX, "te-latn": TE_LATN_LEX}
_LATIN_ORDER = {
    None: ("en", "hinglish", "te-latn"),
    "te": ("en", "te-latn", "hinglish"),
    "te-latn": ("te-latn", "en", "hinglish"),
    "hi": ("hinglish", "en", "te-latn"),
    "hinglish": ("hinglish", "en", "te-latn"),
    "en": ("en", "hinglish", "te-latn"),
}
_TE_LATN_SUFFIXES = sorted(
    ["ki", "ku", "lo", "ni", "nu", "to", "ga", "ke", "daka", "varaku", "nunchi", "lopu", "loga", "kala"],
    key=len, reverse=True,
)


_LANG_CODES = {
    "te": "te", "te-in": "te", "telugu": "te",
    "te-latn": "te-latn", "te-roman": "te-latn", "tenglish": "te-latn", "te-rom": "te-latn",
    "hi": "hi", "hi-in": "hi", "hindi": "hi",
    "hinglish": "hinglish", "hi-latn": "hinglish", "hi-en": "hinglish",
    "en": "en", "en-in": "en", "english": "en",
}


def canon_lang(lang: str | None, strict: bool = True) -> str | None:
    """te | te-latn | hi | hinglish | en (accepts te-IN, hi-IN, en-IN ...)."""
    if lang is None:
        return None
    x = lang.strip().lower().replace("_", "-")
    if x in _LANG_CODES:
        return _LANG_CODES[x]
    if strict:
        raise ValueError(f"unsupported language {lang!r}; use te, hi, hinglish or en")
    return None


@lru_cache(maxsize=65536)
def _lookup_latin(word: str, order) -> tuple[Lex, ...] | None:
    k = skel(word)
    if not k:
        return None
    for name in order:
        hit = LATIN_LEXICONS[name].get(k)
        if hit is not None:
            return hit
    # romanised Telugu: rendunnara (2.5), lakshannara (1.5 lakh), velaki (vela + ki)
    if k.endswith("nara") and len(k) > 4:
        base = TE_LATN_LEX.get(k[:-4]) or EN_LEX.get(k[:-4])
        if base and len(base) == 1:
            b = base[0]
            if b.kind == "num":
                return (Lex("num", b.value + Fraction(1, 2)),)
            if b.kind == "mult":
                return (Lex("mult", b.value, half=True),)
    for suf in _TE_LATN_SUFFIXES:
        if k.endswith(suf) and len(k) > len(suf) + 1:
            base = TE_LATN_LEX.get(k[: -len(suf)])
            if base is not None and base[0].kind in ("mult", "cur"):
                return base
    return None


def lookup_word(tok: Tok, order=_LATIN_ORDER[None]) -> tuple[Lex, ...] | None:
    if tok.kind != "word":
        return None
    if tok.script == "telu":
        return _lookup_te(tok.w)
    if tok.script == "deva":
        return HI_LEX.get(norm_deva(tok.w))
    return _lookup_latin(tok.w, order)


def latin_order(lang_hint: str | None):
    return _LATIN_ORDER[canon_lang(lang_hint, strict=False)]


# ===========================================================================
# 3. Output: format and spell out
# ===========================================================================
def _check_amount(amount) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError(f"amount must be an int, got {type(amount).__name__}")
    if amount < 0 or amount > MAX_INR:
        raise ValueError(f"amount {amount} outside 0..{MAX_INR}")
    return amount


def format_inr(amount: int) -> str:
    """₹ with Indian digit grouping: 120000 -> "₹1,20,000"."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError(f"amount must be an int, got {type(amount).__name__}")
    sign = "-" if amount < 0 else ""
    s = str(abs(amount))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return f"{sign}₹{s}"


def _split_indian(n: int):
    crore, rem = divmod(n, CRORE)
    lakh, rem = divmod(rem, LAKH)
    thou, rem = divmod(rem, 1000)
    hund, rest = divmod(rem, 100)
    return crore, lakh, thou, hund, rest


def _needs_and(n: int) -> bool:
    """1,00,020 / 2,00,00,005: the part after lakh/crore is a bare 1..99.
    Said without "and" it would be heard (and parsed) as 1,20,000."""
    crore, lakh, thou, hund, rest = _split_indian(n)
    return bool(rest) and not thou and not hund and (lakh > 0 or crore > 0)


def _te_1_99(n: int, one: str) -> str:
    """1..99 in Telugu. ``one`` is the form used for a trailing 1 (21, 31 ...)."""
    if n < 20:
        return one if n == 1 else TE_UNITS[n]
    t, u = divmod(n, 10)
    if u == 0:
        return TE_TENS[n]
    return f"{TE_TENS[t * 10]} {one if u == 1 else TE_UNITS[u]}"


def _te_words(n: int, currency: bool) -> str:
    if n == 0:
        return f"{TE_UNITS[0]} {TE_RUPEES}" if currency else TE_UNITS[0]
    if n == 1 and currency:
        return f"{TE_ONE_ATTR} {TE_RUPEE}"
    comps = [(c, u) for c, u in zip(_split_indian(n), ("crore", "lakh", "thousand", "hundred", "rest")) if c]
    words: list[str] = []
    use_and = _needs_and(n)
    for idx, (c, unit) in enumerate(comps):
        last = idx == len(comps) - 1
        oblique = (not last) or currency  # వేల / లక్షల before more words or రూపాయలు
        if use_and and idx == len(comps) - 2:
            oblique = False  # రెండు లక్షలు మరియు ఇరవై
        if unit == "rest":
            if use_and:
                words.append(TE_AND)
            words.append(_te_1_99(c, TE_ONE_COMPOUND if currency else TE_UNITS[1]))
        elif unit == "hundred":
            if c == 1:
                words.append(TE_HUNDRED if last else TE_HUNDRED_PREFIX)
            else:
                words.append(f"{TE_UNITS[c]} {TE_HUNDREDS_OBL if oblique else TE_HUNDREDS}")
        else:
            single, plural, obl = {
                "thousand": (TE_THOUSAND, TE_THOUSANDS, TE_THOUSANDS_OBL),
                "lakh": (f"{TE_ONE_ATTR} {TE_LAKH}", TE_LAKHS, TE_LAKHS_OBL),
                "crore": (f"{TE_ONE_ATTR} {TE_CRORE}", TE_CRORES, TE_CRORES_OBL),
            }[unit]
            if c == 1:
                words.append(single)
            else:
                words.append(f"{_te_1_99(c, TE_ONE_COMPOUND)} {obl if oblique else plural}")
    out = " ".join(words)
    return f"{out} {TE_RUPEES}" if currency else out


def _hi_words(n: int, currency: bool, latin: bool) -> str:
    tbl = HINGLISH_1_99 if latin else HI_1_99
    names = (HG_CRORE, HG_LAKH, HG_THOUSAND, HG_HUNDRED) if latin else (HI_CRORE, HI_LAKH, HI_THOUSAND, HI_HUNDRED)
    rupees, rupee = (HG_RUPEES, HG_RUPEE) if latin else (HI_RUPEES, HI_RUPEE)
    if n == 0:
        out = tbl[0]
    else:
        crore, lakh, thou, hund, rest = _split_indian(n)
        parts = []
        for c, name in zip((crore, lakh, thou, hund), names):
            if c:
                parts.append(f"{tbl[c]} {name}")
        if rest:
            if _needs_and(n):
                parts.append("aur" if latin else "और")
            parts.append(tbl[rest])
        out = " ".join(parts)
    if currency:
        out += " " + (rupee if n == 1 else rupees)
    return out


def _en_1_99(n: int) -> str:
    if n < 20:
        return EN_ONES[n]
    t, u = divmod(n, 10)
    return EN_TENS[n] if u == 0 else f"{EN_TENS[t * 10]} {EN_ONES[u]}"


def _en_words(n: int, currency: bool) -> str:
    if n == 0:
        out = "zero"
    else:
        crore, lakh, thou, hund, rest = _split_indian(n)
        parts = []
        for c, name in ((crore, "crore"), (lakh, "lakh"), (thou, "thousand"), (hund, "hundred")):
            if c:
                parts.append(f"{_en_1_99(c)} {name}")
        if rest:
            if _needs_and(n):
                parts.append("and")
            parts.append(_en_1_99(rest))
        out = " ".join(parts)
    if currency:
        out += " rupee" if n == 1 else " rupees"
    return out


def number_to_words(n: int, lang: str) -> str:
    """Spell ``n`` (0..99,99,99,999) in the lakh/crore system, no currency word."""
    n = _check_amount(n)
    lang = canon_lang(lang)
    if lang in ("te", "te-latn"):
        return _te_words(n, currency=False)
    if lang in ("hi", "hinglish"):
        return _hi_words(n, currency=False, latin=(lang == "hinglish"))
    return _en_words(n, currency=False)


def inr_to_words(amount: int, lang: str) -> str:
    """Rupee amount for TTS read-back.

    te: 65000 -> "అరవై ఐదు వేల రూపాయలు"; hi: "एक लाख बीस हज़ार रुपये";
    hinglish: "ek lakh bees hazaar rupaye"; en: "one lakh twenty thousand rupees".
    """
    amount = _check_amount(amount)
    lang = canon_lang(lang)
    if lang in ("te", "te-latn"):
        return _te_words(amount, currency=True)
    if lang in ("hi", "hinglish"):
        return _hi_words(amount, currency=True, latin=(lang == "hinglish"))
    return _en_words(amount, currency=True)


# ===========================================================================
# 4. Scanning: tokens -> numeric annotations -> number phrases
# ===========================================================================
@dataclass
class NT:
    """One numeric piece. A word like ఐదొందలు yields two NTs (5, x100)."""

    kind: str  # num | mult | frac | adj | addhalf | conn
    value: Fraction | None
    ti: int  # index of the token it came from
    is_digit: bool = False
    commas: bool = False
    tens: bool = False
    needs_coef: bool = False
    half: bool = False


@dataclass
class Ann:
    nts: tuple[NT, ...] | None = None
    role: str | None = None  # cur | curpre | cursuf | conn | range | ordsuf | article
    ordinal: bool = False  # a digit token written as an ordinal: 15th, 15వ, 15న
    ambiguous: bool = False


@dataclass
class Phrase:
    nts: list[NT]
    ti0: int
    ti1: int  # inclusive
    start: int
    end: int
    value: Fraction | None
    approx: bool = False

    @property
    def has_mult(self) -> bool:
        return any(n.kind == "mult" for n in self.nts)

    @property
    def has_word(self) -> bool:
        return any(not n.is_digit and n.kind in ("num", "frac", "adj", "addhalf") for n in self.nts)

    @property
    def has_commas(self) -> bool:
        return any(n.commas for n in self.nts)

    @property
    def small_bare(self) -> bool:
        return (not self.has_mult and not self.has_commas and self.value is not None and self.value < 100)


# Words after which a following ambiguous number word is still a number.
COUNTER_WORDS_LATIN = {skel(w) for w in [
    "din", "dino", "dinon", "day", "days", "hafte", "hafta", "haftey", "week", "weeks", "mahine", "mahina",
    "mahino", "month", "months", "saal", "sal", "year", "years", "tarikh", "tareekh", "tarik", "tareek",
    "taarikh", "date", "baje", "ghante", "ghanta", "minute", "minutes", "roju", "rojulu", "rojullo", "nela",
    "nelalu", "varam", "vaaram", "log", "rooms", "room", "kamre", "kamra",
]}
COUNTER_WORDS_NATIVE = {norm_deva(w) for w in ["दिन", "हफ्ते", "हफ़्ते", "महीने", "महीना", "साल", "तारीख", "बजे", "घंटे", "कमरे"]} | {
    norm_telu(w) for w in ["రోజులు", "రోజుల్లో", "రోజుల", "రోజు", "నెలలు", "నెల", "వారం", "తేదీ", "తారీఖు", "గంటలకు"]
}
_DO_VERBS = {skel(w) for w in ["kar", "karo", "de", "le", "bata", "bhej", "dila", "chhod", "rakh", "laga",
                                "nikal", "karva", "karwa", "kara", "dikha", "sun", "bol", "kah", "bhar", "jama"]}
_LATIN_ORD_SUFFIX = {"st", "nd", "rd", "th"}
_TE_ORD_SUFFIX = {"వ", "వది", "న", "వ్", "ో", "వా"}


def _num_value(w: str) -> Fraction:
    return Fraction(w.replace(",", ""))


def annotate(toks: list[Tok], lang_hint: str | None = None, resolve_ambiguous: bool = True) -> list[Ann]:
    order = latin_order(lang_hint)
    n = len(toks)
    anns = [Ann() for _ in toks]
    for i, t in enumerate(toks):
        a = anns[i]
        prev = toks[i - 1] if i else None
        if t.kind == "num":
            a.nts = (NT("num", _num_value(t.w), i, is_digit=True, commas=("," in t.w)),)
            continue
        if t.kind == "sym":
            if t.w == "₹":
                a.role = "curpre"
            elif t.w == "/" and i + 1 < n and toks[i + 1].w == "-" and toks[i + 1].start == t.end:
                a.role = "cursuf"
            elif t.w == "-" and prev is not None and prev.w == "/" and prev.end == t.start:
                a.role = "cursuf"
            elif t.w == "-":
                a.role = "conn"
            continue
        low = t.low
        attached = prev is not None and prev.kind == "num" and t.start - prev.end <= 1
        prev_int = attached and "." not in prev.w and "," not in prev.w
        if t.script == "latin":
            if low in _LATIN_ORD_SUFFIX and prev_int:
                anns[i - 1].ordinal = True
                anns[i - 1].nts = None
                a.role = "ordsuf"
                continue
            if low == "k" and (attached or (prev is not None and t.start - prev.end <= 1 and anns[i - 1].nts
                                            and anns[i - 1].nts[-1].kind == "num")):
                a.nts = (NT("mult", Fraction(1000), i),)  # 55k, 55 K, forty K
                continue
            if low == "l" and attached and t.start == prev.end:
                a.nts = (NT("mult", Fraction(LAKH), i),)
                continue
            if low in ("a", "an"):
                a.role = "article"
                continue
        elif t.script == "telu" and prev_int and t.start == prev.end and norm_telu(t.w) in _TE_ORD_SUFFIX:
            anns[i - 1].ordinal = True
            anns[i - 1].nts = None
            a.role = "ordsuf"
            continue
        lex = lookup_word(t, order)
        if lex is None:
            continue
        k0 = lex[0].kind
        if k0 == "cur":
            a.role = "cur"
        elif k0 == "conn":
            a.role = "conn"
        elif k0 == "range":
            a.role = "range"
        else:
            a.nts = tuple(NT(x.kind, x.value, i, tens=x.tens, needs_coef=x.needs_coef, half=x.half) for x in lex)
            a.ambiguous = any(x.ambiguous for x in lex)

    # articles and "and a half"
    for i, t in enumerate(toks):
        if anns[i].role != "article":
            continue
        nxt = anns[i + 1] if i + 1 < n else None
        prev_a = anns[i - 1] if i else None
        if nxt is not None and nxt.nts and nxt.nts[0].kind == "mult":
            if prev_a is not None and prev_a.nts and prev_a.nts[-1].kind == "frac":
                anns[i].role = "conn"  # half a lakh
            else:
                anns[i].role = None
                anns[i].nts = (NT("num", Fraction(1), i),)  # a lakh
        elif (nxt is not None and nxt.nts and toks[i + 1].low == "half" and i > 0
              and toks[i - 1].low == "and" and i > 1 and anns[i - 2].nts):
            anns[i].role = "conn"
            anns[i + 1].nts = (NT("addhalf", None, i + 1),)  # one and a half
        else:
            anns[i].role = None

    if resolve_ambiguous:
        for i in range(n - 1, -1, -1):
            a = anns[i]
            if not (a.nts and a.ambiguous):
                continue
            ok = False
            if i + 1 < n and toks[i + 1].kind == "word" and toks[i + 1].start - toks[i].end <= 1:
                b, tb = anns[i + 1], toks[i + 1]
                if b.nts or b.role == "cur":
                    ok = True
                elif tb.script == "latin" and skel(tb.w) in COUNTER_WORDS_LATIN:
                    ok = True
                elif tb.script != "latin" and key_for(tb.w, tb.script) in COUNTER_WORDS_NATIVE:
                    ok = True
            if ok and toks[i].low == "do" and i > 0 and skel(toks[i - 1].w) in _DO_VERBS:
                ok = False
            if not ok:
                a.nts = None
    return anns


def compose(nts: list[NT]) -> Fraction | None:
    """Combine numeric pieces into one value, or None if they do not form one
    number (e.g. "do teen" = "a few", "sau sau", "lakh hazaar lakh")."""
    total = Fraction(0)
    last_big: Fraction | None = None
    h: Fraction | None = None  # hundreds part of the current group
    s: Fraction | None = None  # 0..99 part (or a digit token) of the current group
    s_open = False  # s is a tens word that can still take a unit (ఇరవై + ఐదు)
    s_frac = False
    adj: Fraction | None = None  # sava / sade / paune waiting for its number
    seen = False
    conn_since_big = False
    for t in nts:
        k = t.kind
        if k == "conn":
            conn_since_big = True
            continue
        seen = True
        if k == "adj":
            if adj is not None or s is not None:
                return None
            adj = t.value
            continue
        if k in ("num", "frac"):
            v = t.value
            if s is None:
                if adj is not None:
                    if k == "frac" or v.denominator != 1:
                        return None
                    v = v + adj
                    adj = None
                    s_frac = True
                else:
                    s_frac = k == "frac" or v.denominator != 1
                if h is not None and v >= 100:
                    return None
                s = v
                s_open = t.tens and not t.is_digit
                continue
            if s_open and k == "num" and not t.is_digit and v.denominator == 1 and 1 <= v <= 9:
                s += v
                s_open = False
                continue
            return None
        if k == "addhalf":
            if s is None or s_frac:
                return None
            s += Fraction(1, 2)
            s_frac = True
            s_open = False
            continue
        if k == "mult":
            m = t.value
            coef = s
            if adj is not None:
                coef = 1 + adj
                adj = None
            if t.half:
                coef = (coef if coef is not None else Fraction(1)) + Fraction(1, 2)
            if m == 100:
                if h is not None:
                    return None
                if coef is None:
                    if t.needs_coef:
                        return None
                    coef = Fraction(1)
                if coef >= 100:
                    return None
                h = coef * 100
            else:
                if last_big is not None and m >= last_big:
                    return None
                if h is None and coef is None:
                    if t.needs_coef:
                        return None
                    group = Fraction(1)
                else:
                    group = (h or 0) + (coef or 0)
                total += group * m
                last_big = m
                h = None
                conn_since_big = False
            s = None
            s_open = False
            s_frac = False
            continue
        return None
    if not seen or adj is not None:
        return None
    # "lakh-short": ek lakh bees / laksha iravai / లక్షా ఇరవై = 1,20,000 and
    # do crore paanch = 2,05,00,000. Speakers drop the next unit word. An
    # explicit "and" (ek lakh aur bees) keeps the literal 1,00,020.
    if last_big in (LAKH, CRORE) and h is None and s is not None and not s_frac and not conn_since_big \
            and s.denominator == 1 and 1 <= s <= 99:
        return total + s * (last_big / 100)
    tail = (h or 0) + (s or 0)
    if last_big is not None and tail >= last_big:
        return None
    return total + tail


def _smallish(t: NT) -> bool:
    return t.kind in ("num", "frac") and (not t.is_digit or (t.value < 100 and not t.commas))


def _segment(nts: list[NT]) -> list[list]:
    """Split a run that does not compose into the longest valid pieces.
    Two small numbers side by side ("do teen", "20 25", "2-3") mark both
    neighbours as approximate."""
    res: list[list] = []
    i, n = 0, len(nts)
    while i < n:
        while i < n and nts[i].kind == "conn":
            i += 1
        if i >= n:
            break
        best = None
        for j in range(n, i, -1):
            if nts[j - 1].kind == "conn":
                continue
            if compose(nts[i:j]) is not None:
                best = j
                break
        if best is None:
            best = i + 1
        res.append([i, best, False])
        i = best
    for a in range(len(res) - 1):
        left = nts[res[a][1] - 1]
        right = nts[res[a + 1][0]]
        if _smallish(left) and _smallish(right):
            res[a][2] = True
            res[a + 1][2] = True
    return res


def find_phrases(toks: list[Tok], anns: list[Ann]) -> list[Phrase]:
    n = len(toks)

    def numeric(i: int) -> bool:
        return bool(anns[i].nts)

    def numeric_ahead(i: int) -> bool:
        j = i + 1
        while j < n and anns[j].role == "conn" and not anns[j].nts:
            j += 1
        return j < n and numeric(j)

    runs: list[list[NT]] = []
    cur: list[NT] = []
    for i in range(n):
        a = anns[i]
        if a.nts:
            cur.extend(a.nts)
        elif a.role == "conn" and cur and numeric_ahead(i):
            cur.append(NT("conn", None, i))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)

    phrases: list[Phrase] = []
    for run in runs:
        whole = compose(run)
        pieces = [[0, len(run), False]] if whole is not None else _segment(run)
        for i0, i1, approx in pieces:
            sub = run[i0:i1]
            while sub and sub[-1].kind == "conn":
                sub.pop()
            if not sub:
                continue
            ti0, ti1 = sub[0].ti, sub[-1].ti
            phrases.append(Phrase(sub, ti0, ti1, toks[ti0].start, toks[ti1].end, compose(sub), approx))

    # "2 se 3 lakh", "do ya teen hazaar", "1 to 2 lakh": a range, not an amount
    for p, q in zip(phrases, phrases[1:]):
        if q.ti0 - p.ti1 == 2 and anns[p.ti1 + 1].role in ("range", "conn") and p.small_bare and q.has_mult \
                and _smallish(q.nts[0]):
            p.approx = q.approx = True
    return phrases


def scan(text: str, lang_hint: str | None = None, resolve_ambiguous: bool = True):
    """Tokenise + annotate + find phrases. Returns (work, toks, anns, phrases)."""
    work = work_text(text)
    toks = tokenize(work, text)
    anns = annotate(toks, lang_hint, resolve_ambiguous=resolve_ambiguous)
    return work, toks, anns, find_phrases(toks, anns)


# ===========================================================================
# 5. words -> number
# ===========================================================================
def words_to_number(text: str, lang: str | None = None) -> int | None:
    """Value of the first exact number phrase in ``text`` (words, digits or a
    mix: "ek lakh bees hazaar", "55 vela", "రెండున్నర లక్షలు", "2.5 lakh",
    "55k"). Returns None when there is none, when it is approximate
    ("do teen hazaar") or when it is not a whole number ("dedh")."""
    lang = canon_lang(lang) if lang is not None else None
    _, _, _, phrases = scan(text, lang, resolve_ambiguous=False)
    for p in phrases:
        if p.approx or p.value is None:
            continue
        if p.value.denominator != 1:
            return None
        return int(p.value)
    return None


def te_words_to_number(text: str) -> int | None:
    """Telugu script (mixed with digits/English is fine): "లక్ష ఇరవై వేలు"."""
    return words_to_number(text, "te")


def te_roman_words_to_number(text: str) -> int | None:
    """Romanised Telugu: "yabhai aidu vela", "rendu lakshalu", "55 vela"."""
    return words_to_number(text, "te-latn")


def hi_words_to_number(text: str) -> int | None:
    """Hindi in Devanagari: "एक लाख बीस हज़ार", "डेढ़ लाख"."""
    return words_to_number(text, "hi")


def hinglish_words_to_number(text: str) -> int | None:
    """Hinglish in Latin: "ek lakh bees hazaar", "sava lakh", "dhai lakh"."""
    return words_to_number(text, "hinglish")


def en_words_to_number(text: str) -> int | None:
    """English, Indian system: "one lakh twenty thousand", "2.5 lakh", "55k"."""
    return words_to_number(text, "en")


__all__ = [
    "MAX_INR", "format_inr", "number_to_words", "inr_to_words", "words_to_number",
    "te_words_to_number", "te_roman_words_to_number", "hi_words_to_number",
    "hinglish_words_to_number", "en_words_to_number",
]
