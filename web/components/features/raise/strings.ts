// Haq Raise strings. Worker side in her UI language; employer side in the employer's language.
// Hinglish is Devanagari with common English words, as in lib/i18n.
import type { RaiseLang } from "@/lib/features/raise";

type Fn<A extends unknown[]> = (...a: A) => string;

export type WorkerStrings = {
  title: string;
  yourPay: string;
  legalFor: Fn<[string]>;
  estimate: string;
  perMonth: string;
  yearHero: string;
  yearLine: Fn<[string]>;
  perDay: Fn<[string]>;
  noGap: string;
  pickPlan: string;
  planFull: string;
  planFullLine: Fn<[string, string]>;
  planStep: string;
  planStepLine: Fn<[string, string, number]>;
  edit: string;
  editTitle: string;
  firstStep: string;
  fullAmount: string;
  months: string;
  save: string;
  years: string;
  yearsHint: string;
  lawToggle: string;
  lawHint: string;
  personal: string;
  personalHint: string;
  tapToSpeak: string;
  listening: string;
  remove: string;
  make: string;
  making: string;
  remake: string;
  messageTitle: Fn<[string]>;
  whatItSays: string;
  listen: string;
  tapToPlay: string;
  send: Fn<[string]>;
  sentWaiting: Fn<[string]>;
  played: Fn<[string]>;
  replied: Fn<[string]>;
  agreed: Fn<[string]>;
  newPay: string;
  fromMonth: Fn<[string]>;
  thenMonth: Fn<[string, string]>;
  agreement: string;
  yearWon: Fn<[string]>;
  ok: string;
  loading: string;
  error: string;
  retry: string;
  notAdvice: string;
  langName: Record<RaiseLang, string>;
  voiceFailed: string;
  copied: string;
  work: Record<string, string>;
  hoursDay: Fn<[string]>;
};

const W: Record<RaiseLang, WorkerStrings> = {
  en: {
    title: "Ask for a raise",
    yourPay: "Your pay",
    legalFor: (h) => `Legal minimum for ${h} h/day`,
    estimate: "estimate",
    perMonth: "a month",
    yearHero: "more every year",
    yearLine: (n) => `That's ${n} more every year`,
    perDay: (n) => `For them it is about ${n} a working day`,
    noGap: "This home already pays at least the legal estimate. Nothing to ask here.",
    pickPlan: "How do you want to ask?",
    planFull: "Ask for the full amount now",
    planFullLine: (a, s) => `${a} a month from ${s}`,
    planStep: "Step it up",
    planStepLine: (a, b, n) => `${a} now → ${b} in ${n} months`,
    edit: "Edit",
    editTitle: "Change the amounts",
    firstStep: "First step (₹ a month)",
    fullAmount: "Full amount (₹ a month)",
    months: "Months until the full amount",
    save: "Save",
    years: "Years in this home",
    yearsHint: "Optional. Mentioned warmly in the message.",
    lawToggle: "Mention the legal minimum in my message",
    lawHint: "Off is safer: a raise request that cites the law can sound like a threat.",
    personal: "Add a line in your own words",
    personalHint: "Optional. Baaki puts it in their language.",
    tapToSpeak: "Tap to speak",
    listening: "Listening…",
    remove: "Remove",
    make: "Make my message",
    making: "Writing your message…",
    remake: "Change",
    messageTitle: (l) => `Your message, in ${l}`,
    whatItSays: "What it says",
    listen: "Listen",
    tapToPlay: "Tap to play",
    send: (e) => `Send to ${e}`,
    sentWaiting: (e) => `Sent. Waiting for ${e}.`,
    played: (e) => `${e} listened to your message.`,
    replied: (e) => `${e} replied`,
    agreed: (e) => `${e} said yes!`,
    newPay: "New pay",
    fromMonth: (m) => `from ${m}`,
    thenMonth: (a, m) => `then ${a} from ${m}`,
    agreement: "Pay agreement (PDF)",
    yearWon: (n) => `${n} more every year`,
    ok: "OK",
    loading: "Loading…",
    error: "Could not load this home.",
    retry: "Try again",
    notAdvice: "Legal figure: Baaki's estimate from Telangana G.O.Ms.No.6 (part-time pro-rated). Baaki is not a lawyer.",
    langName: { "hi-en": "Hinglish", "te-IN": "Telugu", en: "English" },
    voiceFailed: "Voice note not ready; the text still works.",
    copied: "Copied. Paste it in WhatsApp.",
    work: { maid: "Cleaning", cooking: "Cooking", both: "Cooking and cleaning", care: "Child or elder care" },
    hoursDay: (h) => `${h} h a day`,
  },
  "hi-en": {
    title: "Salary बढ़वाएँ",
    yourPay: "आपकी salary",
    legalFor: (h) => `रोज़ ${h} घंटे का न्यूनतम वेतन`,
    estimate: "अनुमान",
    perMonth: "महीना",
    yearHero: "हर साल ज़्यादा",
    yearLine: (n) => `यानी हर साल ${n} ज़्यादा`,
    perDay: (n) => `उनके लिए हर काम के दिन लगभग ${n}`,
    noGap: "यह घर पहले से न्यूनतम अनुमान जितना या ज़्यादा देता है। यहाँ माँगने की ज़रूरत नहीं।",
    pickPlan: "कैसे माँगें?",
    planFull: "पूरी रकम अभी माँगें",
    planFullLine: (a, s) => `${s} से ${a} महीना`,
    planStep: "धीरे-धीरे बढ़ाएँ",
    planStepLine: (a, b, n) => `अभी ${a} → ${n} महीने में ${b}`,
    edit: "बदलें",
    editTitle: "रकम बदलें",
    firstStep: "पहला कदम (₹ महीना)",
    fullAmount: "पूरी रकम (₹ महीना)",
    months: "पूरी रकम कितने महीने में",
    save: "Save",
    years: "इस घर में कितने साल से",
    yearsHint: "ज़रूरी नहीं। Message में प्यार से बताया जाएगा।",
    lawToggle: "मेरे message में न्यूनतम वेतन बताएँ",
    lawHint: "बंद रखना बेहतर है: कानून का ज़िक्र धमकी जैसा लग सकता है।",
    personal: "अपने शब्दों में एक बात जोड़ें",
    personalHint: "ज़रूरी नहीं। Baaki इसे उनकी भाषा में लिखेगा।",
    tapToSpeak: "बोलने के लिए दबाएँ",
    listening: "सुन रहे हैं…",
    remove: "हटाएँ",
    make: "मेरा message बनाएँ",
    making: "Message बन रहा है…",
    remake: "बदलें",
    messageTitle: (l) => `आपका message, ${l} में`,
    whatItSays: "इसमें क्या लिखा है",
    listen: "सुनें",
    tapToPlay: "चलाने के लिए दबाएँ",
    send: (e) => `${e} को भेजें`,
    sentWaiting: (e) => `भेज दिया। ${e} के जवाब का इंतज़ार।`,
    played: (e) => `${e} ने आपका message सुन लिया।`,
    replied: (e) => `${e} का जवाब`,
    agreed: (e) => `${e} ने हाँ कह दिया!`,
    newPay: "नई salary",
    fromMonth: (m) => `${m} से`,
    thenMonth: (a, m) => `फिर ${m} से ${a}`,
    agreement: "वेतन समझौता (PDF)",
    yearWon: (n) => `हर साल ${n} ज़्यादा`,
    ok: "OK",
    loading: "Load हो रहा है…",
    error: "यह घर load नहीं हुआ।",
    retry: "फिर कोशिश करें",
    notAdvice: "न्यूनतम वेतन: Telangana G.O.Ms.No.6 से Baaki का अनुमान (part-time के हिसाब से)। Baaki वकील नहीं है।",
    langName: { "hi-en": "Hinglish", "te-IN": "तेलुगु", en: "English" },
    voiceFailed: "Voice note अभी तैयार नहीं; text भेज सकते हैं।",
    copied: "Copy हो गया। WhatsApp में paste करें।",
    work: { maid: "सफ़ाई", cooking: "खाना बनाना", both: "खाना और सफ़ाई", care: "देखभाल" },
    hoursDay: (h) => `रोज़ ${h} घंटे`,
  },
  "te-IN": {
    title: "జీతం పెంపు అడగండి",
    yourPay: "మీ జీతం",
    legalFor: (h) => `రోజుకు ${h} గంటలకు కనీస వేతనం`,
    estimate: "అంచనా",
    perMonth: "నెలకు",
    yearHero: "ప్రతి సంవత్సరం ఎక్కువ",
    yearLine: (n) => `అంటే ప్రతి సంవత్సరం ${n} ఎక్కువ`,
    perDay: (n) => `వారికి ప్రతి పని రోజుకు సుమారు ${n}`,
    noGap: "ఈ ఇల్లు ఇప్పటికే కనీస అంచనా కంటే ఎక్కువ ఇస్తోంది. ఇక్కడ అడగాల్సింది లేదు.",
    pickPlan: "ఎలా అడగాలి?",
    planFull: "మొత్తం ఇప్పుడే అడగండి",
    planFullLine: (a, s) => `${s} నుండి నెలకు ${a}`,
    planStep: "దశలవారీగా",
    planStepLine: (a, b, n) => `ఇప్పుడు ${a} → ${n} నెలల్లో ${b}`,
    edit: "మార్చండి",
    editTitle: "మొత్తాలు మార్చండి",
    firstStep: "మొదటి దశ (నెలకు ₹)",
    fullAmount: "పూర్తి మొత్తం (నెలకు ₹)",
    months: "పూర్తి మొత్తానికి ఎన్ని నెలలు",
    save: "సేవ్",
    years: "ఈ ఇంట్లో ఎన్ని సంవత్సరాలు",
    yearsHint: "ఐచ్ఛికం. మెసేజ్‌లో ఆప్యాయంగా చెబుతాం.",
    lawToggle: "నా మెసేజ్‌లో కనీస వేతనం చెప్పండి",
    lawHint: "ఆఫ్‌లో ఉంచడం సురక్షితం: చట్టం ప్రస్తావిస్తే బెదిరింపులా వినిపించవచ్చు.",
    personal: "మీ మాటల్లో ఒక మాట చెప్పండి",
    personalHint: "ఐచ్ఛికం. బాకీ దాన్ని వారి భాషలో రాస్తుంది.",
    tapToSpeak: "మాట్లాడటానికి నొక్కండి",
    listening: "వింటున్నాం…",
    remove: "తీసివేయండి",
    make: "నా మెసేజ్ తయారు చేయండి",
    making: "మెసేజ్ తయారవుతోంది…",
    remake: "మార్చండి",
    messageTitle: (l) => `మీ మెసేజ్, ${l}లో`,
    whatItSays: "ఇందులో ఏముంది",
    listen: "వినండి",
    tapToPlay: "ప్లే చేయడానికి నొక్కండి",
    send: (e) => `${e}కి పంపండి`,
    sentWaiting: (e) => `పంపాం. ${e} సమాధానం కోసం ఎదురుచూస్తున్నాం.`,
    played: (e) => `${e} మీ మెసేజ్ విన్నారు.`,
    replied: (e) => `${e} సమాధానం`,
    agreed: (e) => `${e} ఒప్పుకున్నారు!`,
    newPay: "కొత్త జీతం",
    fromMonth: (m) => `${m} నుండి`,
    thenMonth: (a, m) => `తర్వాత ${m} నుండి ${a}`,
    agreement: "జీతం ఒప్పందం (PDF)",
    yearWon: (n) => `ప్రతి సంవత్సరం ${n} ఎక్కువ`,
    ok: "సరే",
    loading: "లోడ్ అవుతోంది…",
    error: "ఈ ఇల్లు లోడ్ కాలేదు.",
    retry: "మళ్ళీ ప్రయత్నించండి",
    notAdvice: "కనీస వేతనం: తెలంగాణ G.O.Ms.No.6 నుండి బాకీ అంచనా (పార్ట్-టైమ్ లెక్క). బాకీ లాయర్ కాదు.",
    langName: { "hi-en": "హిందీ", "te-IN": "తెలుగు", en: "ఇంగ్లీష్" },
    voiceFailed: "వాయిస్ నోట్ ఇంకా సిద్ధం కాలేదు; టెక్స్ట్ పంపవచ్చు.",
    copied: "కాపీ అయింది. WhatsAppలో పేస్ట్ చేయండి.",
    work: { maid: "ఇంటి పని", cooking: "వంట", both: "వంట మరియు ఇంటి పని", care: "సంరక్షణ" },
    hoursDay: (h) => `రోజుకు ${h} గంటలు`,
  },
};

export type EmployerStrings = {
  title: Fn<[string]>;
  listen: Fn<[string]>;
  tapToPlay: string;
  request: string;
  now: string;
  asks: string;
  from: Fn<[string]>;
  then: Fn<[string, string]>;
  why: string;
  accept: string;
  acceptSub: Fn<[string, string]>;
  stepUp: string;
  stepSub: Fn<[string, string, string, string]>;
  talk: string;
  talkHint: Fn<[string]>;
  record: string;
  typeInstead: string;
  typePlaceholder: string;
  sendReply: string;
  sending: string;
  replySent: Fn<[string]>;
  doneTitle: string;
  doneText: Fn<[string, string, string]>;
  agreement: string;
  ics: string;
  notFound: string;
  loading: string;
  yourReplies: string;
  estimate: string;
};

const E: Record<RaiseLang, EmployerStrings> = {
  en: {
    title: (w) => `A message from ${w}`,
    listen: (w) => `Listen to ${w}`,
    tapToPlay: "Tap to play",
    request: "The request",
    now: "Now",
    asks: "Asking",
    from: (m) => `from ${m}`,
    then: (a, m) => `then ${a} from ${m}`,
    why: "Why it matters",
    accept: "Accept",
    acceptSub: (a, m) => `${a} a month from ${m}`,
    stepUp: "Step it up",
    stepSub: (a, s, b, m) => `${a} from ${s}, ${b} from ${m}`,
    talk: "Let's talk",
    talkHint: (w) => `Record a short voice reply. ${w} hears it in her language.`,
    record: "Tap to record",
    typeInstead: "Or type a reply",
    typePlaceholder: "For example: let's talk on Sunday",
    sendReply: "Send reply",
    sending: "Sending…",
    replySent: (w) => `Sent to ${w}, translated into her language.`,
    doneTitle: "Thank you!",
    doneText: (w, a, m) => `${w}'s new salary is ${a} from ${m}. She has been told.`,
    agreement: "Pay agreement (PDF)",
    ics: "Add payday reminder",
    notFound: "This link is not valid any more.",
    loading: "Loading…",
    yourReplies: "Your replies",
    estimate: "estimate",
  },
  "hi-en": {
    title: (w) => `${w} का message`,
    listen: (w) => `${w} की बात सुनें`,
    tapToPlay: "चलाने के लिए दबाएँ",
    request: "उनकी विनती",
    now: "अभी",
    asks: "माँग",
    from: (m) => `${m} से`,
    then: (a, m) => `फिर ${m} से ${a}`,
    why: "क्यों",
    accept: "मंज़ूर है",
    acceptSub: (a, m) => `${m} से ${a} महीना`,
    stepUp: "धीरे-धीरे बढ़ाएँ",
    stepSub: (a, s, b, m) => `${s} से ${a}, ${m} से ${b}`,
    talk: "बात करते हैं",
    talkHint: (w) => `छोटा सा voice जवाब record करें। ${w} इसे अपनी भाषा में सुनेंगी।`,
    record: "Record करने के लिए दबाएँ",
    typeInstead: "या लिखकर जवाब दें",
    typePlaceholder: "जैसे: Sunday को बात करते हैं",
    sendReply: "जवाब भेजें",
    sending: "भेज रहे हैं…",
    replySent: (w) => `${w} को उनकी भाषा में भेज दिया।`,
    doneTitle: "धन्यवाद!",
    doneText: (w, a, m) => `${w} की नई salary ${m} से ${a}। उन्हें बता दिया गया है।`,
    agreement: "वेतन समझौता (PDF)",
    ics: "Payday reminder जोड़ें",
    notFound: "यह link अब काम नहीं करता।",
    loading: "Load हो रहा है…",
    yourReplies: "आपके जवाब",
    estimate: "अनुमान",
  },
  "te-IN": {
    title: (w) => `${w} నుండి మెసేజ్`,
    listen: (w) => `${w} మాట వినండి`,
    tapToPlay: "ప్లే చేయడానికి నొక్కండి",
    request: "వారి విన్నపం",
    now: "ఇప్పుడు",
    asks: "అడుగుతున్నది",
    from: (m) => `${m} నుండి`,
    then: (a, m) => `తర్వాత ${m} నుండి ${a}`,
    why: "ఎందుకు",
    accept: "ఒప్పుకుంటున్నాను",
    acceptSub: (a, m) => `${m} నుండి నెలకు ${a}`,
    stepUp: "దశలవారీగా పెంచుతాను",
    stepSub: (a, s, b, m) => `${s} నుండి ${a}, ${m} నుండి ${b}`,
    talk: "మాట్లాడుకుందాం",
    talkHint: (w) => `చిన్న వాయిస్ సమాధానం రికార్డ్ చేయండి. ${w} దాన్ని తన భాషలో వింటారు.`,
    record: "రికార్డ్ చేయడానికి నొక్కండి",
    typeInstead: "లేదా టైప్ చేయండి",
    typePlaceholder: "ఉదా: ఆదివారం మాట్లాడుకుందాం",
    sendReply: "సమాధానం పంపండి",
    sending: "పంపుతున్నాం…",
    replySent: (w) => `${w}కి వారి భాషలో పంపాం.`,
    doneTitle: "ధన్యవాదాలు!",
    doneText: (w, a, m) => `${w} కొత్త జీతం ${m} నుండి ${a}. వారికి తెలియజేశాం.`,
    agreement: "జీతం ఒప్పందం (PDF)",
    ics: "జీతం రోజు రిమైండర్",
    notFound: "ఈ లింక్ ఇప్పుడు పని చేయదు.",
    loading: "లోడ్ అవుతోంది…",
    yourReplies: "మీ సమాధానాలు",
    estimate: "అంచనా",
  },
};

export function workerStrings(lang: RaiseLang): WorkerStrings {
  return W[lang] ?? W.en;
}

export function employerStrings(lang: RaiseLang): EmployerStrings {
  return E[lang] ?? E.en;
}

/** RaiseCard copy (home screen). */
export const CARD: Record<
  RaiseLang,
  { possible: Fn<[string]>; sub: Fn<[string]>; won: Fn<[string]>; cta: string; needsHours: string; needsHoursSub: Fn<[string]> }
> = {
  en: {
    possible: (n) => `${n} more a year is possible`,
    sub: (e) => `Ask ${e} for a raise, politely, in their language`,
    won: (n) => `${n} more a year, agreed`,
    cta: "Ask for a raise",
    needsHours: "Tell Baaki your hours to see the estimate",
    needsHoursSub: (e) => `Hours at ${e} were not said`,
  },
  "hi-en": {
    possible: (n) => `हर साल ${n} ज़्यादा मिल सकते हैं`,
    sub: (e) => `${e} से प्यार से, उनकी भाषा में salary बढ़ाने को कहें`,
    won: (n) => `हर साल ${n} ज़्यादा, तय हो गया`,
    cta: "Salary बढ़वाएँ",
    needsHours: "अनुमान देखने के लिए Baaki को अपने घंटे बताइए",
    needsHoursSub: (e) => `${e} के यहाँ कितने घंटे, यह नहीं बताया`,
  },
  "te-IN": {
    possible: (n) => `ప్రతి సంవత్సరం ${n} ఎక్కువ రావచ్చు`,
    sub: (e) => `${e}ని మర్యాదగా, వారి భాషలో జీతం పెంచమని అడగండి`,
    won: (n) => `ప్రతి సంవత్సరం ${n} ఎక్కువ, ఒప్పుకున్నారు`,
    cta: "జీతం పెంపు అడగండి",
    needsHours: "అంచనా చూడటానికి మీ పని గంటలు బాకీకి చెప్పండి",
    needsHoursSub: (e) => `${e} దగ్గర ఎన్ని గంటలో చెప్పలేదు`,
  },
};
