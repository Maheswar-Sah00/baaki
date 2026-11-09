// Hisaab Milao page chrome in en / te / hi-en. Every amount, month, read-back and status sentence comes from the
// backend (backend/app/hisaab_core.py); these are only labels around them. Worker pages use her UI language
// (useT); the employer page uses the employer's language (like /e/[token]).
import type { UiLang } from "@/lib/i18n";
import type { HisaabKind } from "@/lib/features/hisaab";

export type WorkerStrings = {
  title: string;
  eyebrow: (employer: string) => string;
  lead: string;
  accent: string;
  sub: (employer: string) => string;
  stillOwed: string;
  total: string;
  paid: string;
  disputed: string;
  notice: string;
  waiting: string;
  saidBy: (name: string) => string;
  theirWords: string;
  listen: string;
  yes: string;
  no: string;
  ifYes: (amount: string) => string;
  exceeds: string;
  decided: string;
  none: string;
  noneHint: (employer: string) => string;
  balance: string;
  cardTitle: (employer: string, n: number) => string;
  cardIdle: string;
  claimTitle: string;
  claimYes: string;
  claimNo: string;
  claimIfYes: (amount: string) => string;
  claimCard: (employer: string, amount: string) => string;
  paidVia: (method: string) => string;
  checkNow: string;
  paisa: string;
  ok: string;
};

const W_EN: WorkerStrings = {
  title: "Hisaab",
  eyebrow: (e) => `Hisaab Milao · ${e}`,
  lead: "Your account,",
  accent: "your call.",
  sub: (e) => `When ${e} remembers a payment differently, it lands here first. Nothing changes until you say yes.`,
  stillOwed: "Still owed",
  total: "Total",
  paid: "Paid",
  disputed: "Disputed",
  notice: "Corrections are said by the employer. Baaki does not check them. You decide.",
  waiting: "Waiting for you",
  saidBy: (n) => `Said by ${n}`,
  theirWords: "Their words",
  listen: "Listen",
  yes: "Yes, I got it",
  no: "No, I didn't",
  ifYes: (a) => `If you say yes, ${a} comes off what is owed.`,
  exceeds: "This is more than what is still owed, so it can't be accepted.",
  decided: "Already decided",
  none: "No corrections waiting.",
  noneHint: (e) => `If ${e} remembers a payment differently, you will see it here first.`,
  balance: "Still owed now",
  cardTitle: (e, n) => `${e} remembers it differently (${n})`,
  cardIdle: "Corrections",
  claimTitle: "Did the money arrive?",
  claimYes: "Yes, it came",
  claimNo: "No, not yet",
  claimIfYes: (a) => `If it came, ${a} is marked as paid. If not, nothing changes.`,
  claimCard: (e, a) => `${e} says he paid ${a}. Did it arrive?`,
  paidVia: (m) => `Paid · ${m}`,
  checkNow: "Check now",
  paisa: "Paisa aa gaya!",
  ok: "Done",
};

const W_TE: WorkerStrings = {
  title: "లెక్క",
  eyebrow: (e) => `లెక్క సరిచూద్దాం · ${e}`,
  lead: "మీ లెక్క,",
  accent: "మీ నిర్ణయం.",
  sub: (e) => `${e} ఏదైనా చెల్లింపును వేరేగా గుర్తుంచుకుంటే, అది ముందు ఇక్కడ కనిపిస్తుంది. మీరు అవును అనే వరకు ఏదీ మారదు.`,
  stillOwed: "ఇంకా బాకీ",
  total: "మొత్తం",
  paid: "చెల్లించారు",
  disputed: "వివాదం",
  notice: "సవరణలు యజమాని చెప్పినవి. బాకీ వాటిని నిర్ధారించదు. మీరే నిర్ణయిస్తారు.",
  waiting: "మీ నిర్ణయం కోసం",
  saidBy: (n) => `${n} చెప్పారు`,
  theirWords: "వారి మాటలు",
  listen: "వినండి",
  yes: "అవును, వచ్చింది",
  no: "లేదు, రాలేదు",
  ifYes: (a) => `అవును అంటే, బాకీ నుండి ${a} తగ్గుతుంది.`,
  exceeds: "ఇది ఇంకా ఉన్న బాకీ కంటే ఎక్కువ, కాబట్టి ఒప్పుకోలేరు.",
  decided: "నిర్ణయించినవి",
  none: "ఎదురుచూస్తున్న సవరణలు లేవు.",
  noneHint: (e) => `${e} ఏదైనా చెల్లింపు వేరేగా గుర్తుంచుకుంటే, ముందు మీకే ఇక్కడ కనిపిస్తుంది.`,
  balance: "ఇప్పుడు ఇంకా బాకీ",
  cardTitle: (e, n) => `${e} వేరేగా గుర్తుంచుకున్నారు (${n})`,
  cardIdle: "సవరణలు",
  claimTitle: "డబ్బులు అందాయా?",
  claimYes: "వచ్చింది",
  claimNo: "రాలేదు",
  claimIfYes: (a) => `వచ్చి ఉంటే, ${a} చెల్లించినట్టు నమోదవుతుంది. లేకపోతే ఏదీ మారదు.`,
  claimCard: (e, a) => `${e} ${a} ఇచ్చామంటున్నారు. డబ్బులు అందాయా?`,
  paidVia: (m) => `చెల్లించారు · ${m}`,
  checkNow: "చూడండి",
  paisa: "డబ్బులు వచ్చేశాయి!",
  ok: "సరే",
};

const W_HI: WorkerStrings = {
  title: "हिसाब",
  eyebrow: (e) => `हिसाब मिलाओ · ${e}`,
  lead: "आपका हिसाब,",
  accent: "आपका फ़ैसला।",
  sub: (e) => `${e} को कोई payment अलग याद है, तो वो पहले यहाँ आता है। जब तक आप हाँ न कहें, कुछ नहीं बदलता।`,
  stillOwed: "अभी बाकी",
  total: "कुल",
  paid: "मिला",
  disputed: "विवादित",
  notice: "Correction मालिक के कहे हुए हैं। Baaki इन्हें जाँचता नहीं। फ़ैसला आपका है।",
  waiting: "आपके फ़ैसले का इंतज़ार",
  saidBy: (n) => `${n} ने कहा`,
  theirWords: "उनके शब्द",
  listen: "सुनें",
  yes: "हाँ, मिला",
  no: "नहीं मिला",
  ifYes: (a) => `हाँ कहने पर बाकी में से ${a} कम होगा।`,
  exceeds: "ये बाकी रकम से ज़्यादा है, इसलिए माना नहीं जा सकता।",
  decided: "तय हो चुके",
  none: "कोई correction इंतज़ार में नहीं।",
  noneHint: (e) => `${e} को कोई payment अलग याद हो, तो पहले यहाँ आपको दिखेगा।`,
  balance: "अब बाकी",
  cardTitle: (e, n) => `${e} को कुछ अलग याद है (${n})`,
  cardIdle: "Corrections",
  claimTitle: "क्या पैसे मिले?",
  claimYes: "हाँ, मिल गए",
  claimNo: "नहीं, अभी नहीं",
  claimIfYes: (a) => `मिल गए हों तो ${a} paid दर्ज होगा। नहीं तो कुछ नहीं बदलेगा।`,
  claimCard: (e, a) => `${e} कहते हैं ${a} दे दिए। क्या पैसे मिले?`,
  paidVia: (m) => `दिए · ${m}`,
  checkNow: "देखें",
  paisa: "पैसा आ गया!",
  ok: "ठीक है",
};

export function workerStrings(lang: UiLang): WorkerStrings {
  return lang === "te" ? W_TE : lang === "hi-en" ? W_HI : W_EN;
}

export type EmployerStrings = {
  title: (worker: string) => string;
  eyebrow: string;
  lead: string;
  accent: string;
  sub: (worker: string) => string;
  stillOwed: (worker: string) => string;
  untilAgree: string;
  speak: string;
  stop: (time: string) => string;
  sending: string;
  example: string;
  orType: string;
  placeholder: string;
  words: string;
  amount: string;
  how: string;
  kinds: Record<HisaabKind | "", string>;
  send: (worker: string) => string;
  heard: string;
  yours: string;
  none: string;
  notice: string;
};

const E_EN: EmployerStrings = {
  title: (w) => `Hisaab · ${w}`,
  eyebrow: "Hisaab Milao",
  lead: "Something's",
  accent: "different?",
  sub: (w) => `Remember a payment differently? Say it in your own words. ${w} hears it in their own language and decides. Nothing changes until they agree.`,
  stillOwed: (w) => `Still owed to ${w}`,
  untilAgree: "Nothing changes until they agree.",
  speak: "Tap to speak",
  stop: (t) => `Stop · ${t}`,
  sending: "Sending…",
  example: "Try: “Maine October mein do hazaar cash diye the”",
  orType: "or type it",
  placeholder: "Maine October mein 2000 cash diye the",
  words: "What you remember",
  amount: "Amount",
  how: "How was it paid?",
  kinds: { "": "From my words", cash: "Cash", upi: "UPI / online", advance: "Advance", other: "Other" },
  send: (w) => `Send to ${w}`,
  heard: "Heard",
  yours: "Your corrections",
  none: "Nothing sent yet.",
  notice: "Baaki does not check corrections. The worker decides.",
};

const E_TE: EmployerStrings = {
  title: (w) => `లెక్క · ${w}`,
  eyebrow: "లెక్క సరిచూద్దాం",
  lead: "ఏదైనా",
  accent: "తేడా ఉందా?",
  sub: (w) => `ఏదైనా చెల్లింపు వేరేగా గుర్తుందా? మీ మాటల్లో చెప్పండి. ${w} తమ భాషలో విని నిర్ణయిస్తారు. వారు ఒప్పుకునే వరకు ఏదీ మారదు.`,
  stillOwed: (w) => `${w}కి ఇంకా బాకీ`,
  untilAgree: "వారు ఒప్పుకునే వరకు ఏదీ మారదు.",
  speak: "నొక్కి మాట్లాడండి",
  stop: (t) => `ఆపండి · ${t}`,
  sending: "పంపుతున్నాం…",
  example: "ఉదా: “అక్టోబర్ లో రెండు వేలు క్యాష్ ఇచ్చాను”",
  orType: "లేదా టైప్ చేయండి",
  placeholder: "అక్టోబర్ లో 2000 క్యాష్ ఇచ్చాను",
  words: "మీకు గుర్తున్నది",
  amount: "మొత్తం",
  how: "ఎలా ఇచ్చారు?",
  kinds: { "": "నా మాటల నుండి", cash: "క్యాష్", upi: "యూపీఐ", advance: "అడ్వాన్స్", other: "ఇతర" },
  send: (w) => `${w}కి పంపండి`,
  heard: "విన్నది",
  yours: "మీ సవరణలు",
  none: "ఇంకా ఏదీ పంపలేదు.",
  notice: "బాకీ సవరణలను నిర్ధారించదు. పనివారే నిర్ణయిస్తారు.",
};

const E_HI: EmployerStrings = {
  title: (w) => `हिसाब · ${w}`,
  eyebrow: "हिसाब मिलाओ",
  lead: "कुछ",
  accent: "अलग याद है?",
  sub: (w) => `कोई payment अलग याद है? अपने शब्दों में बोलिए। ${w} इसे अपनी भाषा में सुनेंगे और तय करेंगे। जब तक वो न मानें, कुछ नहीं बदलता।`,
  stillOwed: (w) => `${w} का अभी बाकी`,
  untilAgree: "जब तक वो न मानें, कुछ नहीं बदलता।",
  speak: "दबाकर बोलें",
  stop: (t) => `रोकें · ${t}`,
  sending: "भेज रहे हैं…",
  example: "जैसे: “Maine October mein do hazaar cash diye the”",
  orType: "या लिखिए",
  placeholder: "Maine October mein 2000 cash diye the",
  words: "आपको क्या याद है",
  amount: "रकम",
  how: "कैसे दिया?",
  kinds: { "": "मेरी बात से", cash: "Cash", upi: "UPI / online", advance: "Advance", other: "कुछ और" },
  send: (w) => `${w} को भेजें`,
  heard: "सुना",
  yours: "आपके corrections",
  none: "अभी कुछ नहीं भेजा।",
  notice: "Baaki corrections को जाँचता नहीं। फ़ैसला काम करने वाले का है।",
};

export function employerStrings(lang: UiLang): EmployerStrings {
  return lang === "te" ? E_TE : lang === "hi-en" ? E_HI : E_EN;
}

/** The worker's own word for yes / no on a payment claim, shown under the English label (Lakshmi: Vachindi / Raledu). */
export const CLAIM_WORDS: Record<UiLang, { yes: string; no: string }> = {
  te: { yes: "Vachindi", no: "Raledu" },
  "hi-en": { yes: "Mil gaye", no: "Nahi mile" },
  en: { yes: "", no: "" },
};

/** Payment kind, shown next to the amount. */
export const KIND_LABEL: Record<UiLang, Record<string, string>> = {
  en: { cash: "Cash", upi: "UPI", advance: "Advance", other: "Other", bank: "Bank" },
  te: { cash: "క్యాష్", upi: "యూపీఐ", advance: "అడ్వాన్స్", other: "ఇతర", bank: "బ్యాంక్" },
  "hi-en": { cash: "Cash", upi: "UPI", advance: "Advance", other: "अन्य", bank: "Bank" },
};

/** html lang attribute for a UI language (Indic fonts + line height). */
export const HTML_LANG: Record<UiLang, string> = { en: "en", te: "te", "hi-en": "hi" };
