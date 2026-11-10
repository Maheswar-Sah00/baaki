// Share to Baaki + Promise Keeper strings: Telugu, Hinglish (Devanagari + English words, as in lib/i18n), English.
import type { UiLang } from "@/lib/i18n";
import type { PromiseStatus } from "@/lib/features/inbox";

export type InboxStrings = {
  entry: string;
  entryHint: string;
  title: string;
  intro: (employer: string) => string;
  add: string;
  sheetTitle: string;
  tabUpload: string;
  tabRecord: string;
  tabPaste: string;
  uploadHint: string;
  chooseFile: string;
  chosen: (name: string) => string;
  recordHint: string;
  recordStart: string;
  recordStop: string;
  recorded: (s: string) => string;
  pastePlaceholder: string;
  langLabel: string;
  langs: Record<"employer" | "auto" | "hi-en" | "te-IN" | "en", string>;
  saidOnLabel: string;
  submit: string;
  working: string;
  empty: string;
  emptyHint: string;
  theySaid: string;
  inYourLang: string;
  listen: string;
  original: string;
  proofSaved: string;
  duplicate: string;
  hash: (h: string) => string;
  status: Record<PromiseStatus, string>;
  promise: string;
  amountNotSaid: string;
  rest: string;
  by: (d: string) => string;
  weekOf: (a: string, b: string) => string;
  confirmQ: string;
  yes: string;
  fix: string;
  save: string;
  cancel: string;
  dateLabel: string;
  amountLabel: string;
  markKept: string;
  markBroken: string;
  passedTitle: string;
  passedBody: (amount: string, date: string) => string;
  makeReminder: string;
  reminderLabel: string;
  reminderMine: string;
  share: string;
  whatsapp: string;
  copied: string;
  checksOk: string;
  youSend: string;
  chainOk: (n: number) => string;
  chainBroken: string;
  audioFailed: string;
  error: string;
  retry: string;
  noPromise: string;
  privacy: string;
  pickTitle: string;
  pickHint: string;
  pickNone: string;
  /** Payments the employer says he already made (read-only; nothing is recorded). */
  pastTitle: string;
  pastNote: string;
  pastCheck: string;
};

export const INBOX_STRINGS: Record<UiLang, InboxStrings> = {
  en: {
    entry: "Got a WhatsApp reply?",
    entryHint: "Share their voice note: hear it in your language, save it as proof",
    title: "WhatsApp replies",
    intro: (e) => `Did ${e} reply on WhatsApp? Add the voice note or the text. Baaki tells you what was said and keeps any promise.`,
    add: "Add a WhatsApp reply",
    sheetTitle: "Add the reply",
    tabUpload: "Voice note",
    tabRecord: "Record",
    tabPaste: "Paste text",
    uploadHint: "In WhatsApp, long-press the voice note, tap Share, then save it. Pick the file here.",
    chooseFile: "Choose the voice note",
    chosen: (n) => `Chosen: ${n}`,
    recordHint: "Play the voice note on speaker and record it here.",
    recordStart: "Start recording",
    recordStop: "Stop",
    recorded: (s) => `Recorded ${s}`,
    pastePlaceholder: "Paste their message here",
    langLabel: "They spoke in",
    langs: { employer: "Their usual language", auto: "Don't know", "hi-en": "Hindi / Hinglish", "te-IN": "Telugu", en: "English" },
    saidOnLabel: "Day they sent it",
    submit: "Hear it in my language",
    working: "Baaki is listening…",
    empty: "No replies yet",
    emptyHint: "When the employer answers on WhatsApp, add it here. Promises they make are tracked for you.",
    theySaid: "Their words",
    inYourLang: "In your language",
    listen: "Listen",
    original: "Their voice note",
    proofSaved: "Saved as proof",
    duplicate: "This reply was already saved",
    hash: (h) => `Proof code ${h}`,
    status: { pending: "Waiting", passed: "Date passed", kept: "Kept", broken: "Not kept" },
    promise: "Promise",
    amountNotSaid: "Amount not said",
    rest: "The rest",
    by: (d) => `by ${d}`,
    weekOf: (a, b) => `week of ${a} – ${b}`,
    confirmQ: "Is this right?",
    yes: "Yes, right",
    fix: "Fix",
    save: "Save",
    cancel: "Cancel",
    dateLabel: "Promised date",
    amountLabel: "Promised amount (₹)",
    markKept: "Paid",
    markBroken: "Not paid",
    passedTitle: "Promise passed: remind?",
    passedBody: (a, d) => `They said ${a} by ${d}. A gentle reminder quotes their own words.`,
    makeReminder: "Make a gentle reminder",
    reminderLabel: "Message for the employer",
    reminderMine: "What it says",
    share: "Share",
    whatsapp: "Open WhatsApp",
    copied: "Copied",
    checksOk: "Amounts checked",
    youSend: "Nothing is sent automatically. You choose to send it.",
    chainOk: (n) => `Proof chain intact · ${n} entries`,
    chainBroken: "Proof chain changed: an entry was edited",
    audioFailed: "Voice not ready. Read it on screen.",
    error: "Could not do that. Try again.",
    retry: "Try again",
    noPromise: "No date was promised in this reply.",
    privacy: "Their voice note stays private to your case.",
    pickTitle: "Which home is this reply from?",
    pickHint: "Pick the employer who sent this voice note.",
    pickNone: "Nothing was shared. Open WhatsApp, long-press the voice note and share it to Baaki.",
    pastTitle: "Payments they mention",
    pastNote: "Only noted here. Nothing is recorded.",
    pastCheck: "Check it",
  },
  te: {
    entry: "WhatsApp లో జవాబు వచ్చిందా?",
    entryHint: "వాళ్ల వాయిస్ నోట్ ఇక్కడ పెట్టండి: మీ భాషలో వినండి, రుజువుగా దాచండి",
    title: "WhatsApp జవాబులు",
    intro: (e) => `${e} WhatsApp లో జవాబు ఇచ్చారా? వాయిస్ నోట్ లేదా మెసేజ్ ఇక్కడ పెట్టండి. ఏం చెప్పారో బాకీ మీకు చెబుతుంది, వాళ్ల మాట గుర్తు పెడుతుంది.`,
    add: "WhatsApp జవాబు పెట్టండి",
    sheetTitle: "జవాబు పెట్టండి",
    tabUpload: "వాయిస్ నోట్",
    tabRecord: "రికార్డ్",
    tabPaste: "మెసేజ్",
    uploadHint: "WhatsApp లో వాయిస్ నోట్ ని నొక్కి పట్టుకుని, Share నొక్కి, సేవ్ చేయండి. ఆ ఫైల్ ఇక్కడ ఎంచుకోండి.",
    chooseFile: "వాయిస్ నోట్ ఎంచుకోండి",
    chosen: (n) => `ఎంచుకున్నది: ${n}`,
    recordHint: "వాయిస్ నోట్ ని స్పీకర్ లో ప్లే చేసి ఇక్కడ రికార్డ్ చేయండి.",
    recordStart: "రికార్డ్ మొదలు",
    recordStop: "ఆపండి",
    recorded: (s) => `రికార్డ్ అయింది ${s}`,
    pastePlaceholder: "వాళ్ల మెసేజ్ ఇక్కడ పేస్ట్ చేయండి",
    langLabel: "వాళ్లు మాట్లాడిన భాష",
    langs: { employer: "వాళ్ల మామూలు భాష", auto: "తెలియదు", "hi-en": "హిందీ / Hinglish", "te-IN": "తెలుగు", en: "ఇంగ్లీష్" },
    saidOnLabel: "పంపిన రోజు",
    submit: "నా భాషలో వినిపించు",
    working: "బాకీ వింటోంది…",
    empty: "ఇంకా జవాబులు లేవు",
    emptyHint: "యజమాని WhatsApp లో జవాబు ఇస్తే ఇక్కడ పెట్టండి. వాళ్లు ఇచ్చిన మాట మీ కోసం గుర్తు ఉంటుంది.",
    theySaid: "వాళ్ల మాటలు",
    inYourLang: "మీ భాషలో",
    listen: "వినండి",
    original: "వాళ్ల వాయిస్ నోట్",
    proofSaved: "రుజువుగా దాచాం",
    duplicate: "ఈ జవాబు ఇంతకు ముందే దాచాం",
    hash: (h) => `రుజువు కోడ్ ${h}`,
    status: { pending: "ఎదురుచూపు", passed: "తేదీ దాటింది", kept: "మాట నిలబెట్టారు", broken: "ఇవ్వలేదు" },
    promise: "మాట",
    amountNotSaid: "మొత్తం చెప్పలేదు",
    rest: "మిగతాది",
    by: (d) => `${d} లోపు`,
    weekOf: (a, b) => `${a} – ${b} వారం`,
    confirmQ: "ఇది సరైనదేనా?",
    yes: "అవును, సరైనది",
    fix: "మార్చండి",
    save: "దాచండి",
    cancel: "వద్దు",
    dateLabel: "మాట ఇచ్చిన తేదీ",
    amountLabel: "మాట ఇచ్చిన మొత్తం (₹)",
    markKept: "ఇచ్చారు",
    markBroken: "ఇవ్వలేదు",
    passedTitle: "తేదీ దాటింది: గుర్తు చేయాలా?",
    passedBody: (a, d) => `${d} లోపు ${a} ఇస్తామన్నారు. వాళ్ల మాటలనే మర్యాదగా గుర్తు చేద్దాం.`,
    makeReminder: "మర్యాదగా గుర్తు చేయండి",
    reminderLabel: "యజమానికి మెసేజ్",
    reminderMine: "అందులో ఏముంది",
    share: "షేర్ చేయండి",
    whatsapp: "WhatsApp తెరవండి",
    copied: "కాపీ అయింది",
    checksOk: "మొత్తాలు సరిచూశాం",
    youSend: "ఏదీ తనంతట తాను వెళ్లదు. పంపాలో లేదో మీరే నిర్ణయించండి.",
    chainOk: (n) => `రుజువు గొలుసు సరిగా ఉంది · ${n} నమోదులు`,
    chainBroken: "రుజువు గొలుసు మారింది: ఒక నమోదు మార్చబడింది",
    audioFailed: "వాయిస్ సిద్ధం కాలేదు. స్క్రీన్ మీద చదవండి.",
    error: "కాలేదు. మళ్ళీ ప్రయత్నించండి.",
    retry: "మళ్ళీ ప్రయత్నించండి",
    noPromise: "ఈ జవాబులో తేదీ ఏదీ చెప్పలేదు.",
    privacy: "వాళ్ల వాయిస్ నోట్ మీ కేసులోనే ఉంటుంది, ఎవరికీ వెళ్లదు.",
    pickTitle: "ఈ జవాబు ఏ ఇంటి నుండి?",
    pickHint: "ఈ వాయిస్ నోట్ పంపిన యజమానిని ఎంచుకోండి.",
    pickNone: "ఏదీ షేర్ కాలేదు. WhatsApp లో వాయిస్ నోట్ ని నొక్కి పట్టుకుని బాకీ కి షేర్ చేయండి.",
    pastTitle: "వాళ్లు చెప్పిన చెల్లింపులు",
    pastNote: "ఇక్కడ చూపడానికి మాత్రమే. ఏదీ నమోదు కాలేదు.",
    pastCheck: "చూడండి",
  },
  "hi-en": {
    entry: "WhatsApp reply आया?",
    entryHint: "उनका voice note यहाँ डालिए: अपनी भाषा में सुनिए, सबूत की तरह रखिए",
    title: "WhatsApp replies",
    intro: (e) => `${e} ने WhatsApp पर जवाब दिया? Voice note या message यहाँ डालिए। Baaki बताएगा क्या कहा, और उनका वादा याद रखेगा।`,
    add: "WhatsApp reply डालिए",
    sheetTitle: "Reply डालिए",
    tabUpload: "Voice note",
    tabRecord: "Record",
    tabPaste: "Message",
    uploadHint: "WhatsApp में voice note को दबाकर रखिए, Share दबाइए, फिर save कीजिए। वह file यहाँ चुनिए।",
    chooseFile: "Voice note चुनिए",
    chosen: (n) => `चुना: ${n}`,
    recordHint: "Voice note को speaker पर चलाइए और यहाँ record कीजिए।",
    recordStart: "Record शुरू",
    recordStop: "रोकिए",
    recorded: (s) => `Record हुआ ${s}`,
    pastePlaceholder: "उनका message यहाँ paste कीजिए",
    langLabel: "उन्होंने बोला",
    langs: { employer: "उनकी आम भाषा", auto: "पता नहीं", "hi-en": "Hindi / Hinglish", "te-IN": "Telugu", en: "English" },
    saidOnLabel: "भेजने का दिन",
    submit: "मेरी भाषा में सुनाओ",
    working: "Baaki सुन रहा है…",
    empty: "अभी कोई reply नहीं",
    emptyHint: "मालिक WhatsApp पर जवाब दें तो यहाँ डालिए। उनके वादे आपके लिए याद रखे जाएँगे।",
    theySaid: "उनके शब्द",
    inYourLang: "आपकी भाषा में",
    listen: "सुनिए",
    original: "उनका voice note",
    proofSaved: "सबूत की तरह रखा",
    duplicate: "यह reply पहले से रखा है",
    hash: (h) => `सबूत code ${h}`,
    status: { pending: "इंतज़ार", passed: "तारीख़ निकल गई", kept: "वादा निभाया", broken: "नहीं दिया" },
    promise: "वादा",
    amountNotSaid: "रकम नहीं बताई",
    rest: "बाकी",
    by: (d) => `${d} तक`,
    weekOf: (a, b) => `${a} – ${b} का हफ़्ता`,
    confirmQ: "क्या यह सही है?",
    yes: "हाँ, सही है",
    fix: "बदलिए",
    save: "Save",
    cancel: "रहने दो",
    dateLabel: "वादे की तारीख़",
    amountLabel: "वादे की रकम (₹)",
    markKept: "दे दिया",
    markBroken: "नहीं दिया",
    passedTitle: "तारीख़ निकल गई: याद दिलाएँ?",
    passedBody: (a, d) => `उन्होंने ${d} तक ${a} देने को कहा था। उन्हीं के शब्दों में आराम से याद दिलाइए।`,
    makeReminder: "आराम से याद दिलाइए",
    reminderLabel: "मालिक के लिए message",
    reminderMine: "इसमें क्या लिखा है",
    share: "Share",
    whatsapp: "WhatsApp खोलिए",
    copied: "Copy हो गया",
    checksOk: "रकम जाँची गई",
    youSend: "कुछ भी अपने-आप नहीं जाता। भेजना है या नहीं, आप तय करें।",
    chainOk: (n) => `सबूत की chain सही है · ${n} entries`,
    chainBroken: "सबूत की chain बदली है: एक entry बदली गई",
    audioFailed: "आवाज़ तैयार नहीं। Screen पर पढ़िए।",
    error: "नहीं हो पाया। फिर कोशिश कीजिए।",
    retry: "फिर कोशिश कीजिए",
    noPromise: "इस reply में कोई तारीख़ नहीं बताई।",
    privacy: "उनका voice note सिर्फ़ आपके case में रहता है।",
    pickTitle: "यह reply किस घर से है?",
    pickHint: "जिस मालिक ने यह voice note भेजा, उन्हें चुनिए।",
    pickNone: "कुछ share नहीं हुआ। WhatsApp में voice note दबाकर रखिए और Baaki पर share कीजिए।",
    pastTitle: "उन्होंने बताए payments",
    pastNote: "सिर्फ़ यहाँ दिखाया है। कुछ भी record नहीं हुआ।",
    pastCheck: "देखिए",
  },
};

export function inboxStrings(lang: UiLang): InboxStrings {
  return INBOX_STRINGS[lang] ?? INBOX_STRINGS.en;
}
