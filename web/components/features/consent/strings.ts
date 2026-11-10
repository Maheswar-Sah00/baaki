// Voice-consent screen chrome in the app's UI language (settings.uiLang: te / hi-en / en).
// The consent SENTENCE itself has its own language switch (CONSENT_LANGS); this is only the text around it.
import type { UiLang } from "@/lib/i18n";

type Parts = { before: string; bold: string; after: string };

export type ConsentUi = {
  title: string;
  eyebrow: string;
  heroLead: string;
  heroAccent: string;
  heroSub: string;
  langGroup: string;
  loading: string;
  noAudio: string;
  readNow: string;
  checking: string;
  sayAfter: string;
  loadingShort: string;
  listenFirst: string;
  stop: string;
  recordAgain: string;
  record: string;
  keepReading: (seconds: number) => string;
  profileReady: string;
  consentOn: (byTap: boolean, when: string) => string;
  consentTap: string;
  consentHeard: string;
  readyText: string;
  wordsHeard: (matched: number, total: number) => Parts;
  nameNotHeard: string;
  savedInDiary: (when: string, hash: string) => string;
  missed: string;
  baakiHeard: (transcript: string) => string;
  tryAgain: string;
  confirmByTap: string;
  lockNote: string;
  withdrawNote: string;
  withdrawBtn: string;
  consentRecord: (n: number) => string;
  logWithdrawn: string;
  logGiven: (method: string) => string;
};

const en: ConsentUi = {
  title: "Voice consent",
  eyebrow: "Say it once",
  heroLead: "Your voice,",
  heroAccent: "your permission.",
  heroSub: "Say this sentence after Baaki. The same recording is your permission and your voice sample.",
  langGroup: "Language",
  loading: "Loading",
  noAudio: "Baaki cannot speak right now. Read the sentence on the screen.",
  readNow: "Read it now, slowly",
  checking: "Checking your words…",
  sayAfter: "Say this after Baaki",
  loadingShort: "Loading…",
  listenFirst: "Listen first",
  stop: "Stop",
  recordAgain: "Record again",
  record: "Record",
  keepReading: (s) => `Keep reading, at least ${s} seconds.`,
  profileReady: "Voice profile ready",
  consentOn: (tap, when) => `Consent ${tap ? "confirmed by tap" : "given by voice"} on ${when} UTC.`,
  consentTap: "Consent confirmed by tap",
  consentHeard: "Consent heard",
  readyText:
    "Your voice profile is ready. Messages to employers can now use your voice, and each one says first that it is an AI message.",
  wordsHeard: (m, t) => ({ before: "", bold: String(m), after: ` of ${t} words heard` }),
  nameNotHeard: ", your name was not heard",
  savedInDiary: (when, hash) => `Saved in your diary: ${when} UTC · hash ${hash}…`,
  missed: "Missed:",
  baakiHeard: (tr) => `Baaki heard: “${tr}”`,
  tryAgain: "Try again",
  confirmByTap: "I agree, confirm by tap",
  lockNote: "Baaki keeps only the voice profile and a fingerprint (hash) of the recording, never the recording.",
  withdrawNote: "You can take back your permission at any time. This deletes your voice profile.",
  withdrawBtn: "Withdraw consent and delete my voice",
  consentRecord: (n) => `Consent record (${n})`,
  logWithdrawn: "withdrawn",
  logGiven: (m) => `given (${m})`,
};

const te: ConsentUi = {
  title: "గొంతు అనుమతి",
  eyebrow: "ఒక్కసారి చెప్పండి",
  heroLead: "మీ గొంతు,",
  heroAccent: "మీ అనుమతి.",
  heroSub: "బాకీ చెప్పిన తర్వాత ఈ వాక్యం చెప్పండి. అదే రికార్డింగ్ మీ అనుమతి, మీ గొంతు నమూనా కూడా.",
  langGroup: "భాష",
  loading: "లోడ్ అవుతోంది",
  noAudio: "బాకీ ఇప్పుడు మాట్లాడలేదు. స్క్రీన్ మీద ఉన్న వాక్యం చదవండి.",
  readNow: "ఇప్పుడు నెమ్మదిగా చదవండి",
  checking: "మీ మాటలు సరిచూస్తోంది…",
  sayAfter: "బాకీ తర్వాత ఇది చెప్పండి",
  loadingShort: "లోడ్ అవుతోంది…",
  listenFirst: "ముందు వినండి",
  stop: "ఆపండి",
  recordAgain: "మళ్ళీ రికార్డ్",
  record: "రికార్డ్",
  keepReading: (s) => `చదువుతూ ఉండండి, కనీసం ${s} సెకన్లు.`,
  profileReady: "గొంతు ప్రొఫైల్ సిద్ధం",
  consentOn: (tap, when) => `${when} UTC న ${tap ? "ట్యాప్‌తో అనుమతి నిర్ధారించారు" : "గొంతుతో అనుమతి ఇచ్చారు"}.`,
  consentTap: "ట్యాప్‌తో అనుమతి నిర్ధారించారు",
  consentHeard: "అనుమతి వినిపించింది",
  readyText:
    "మీ గొంతు ప్రొఫైల్ సిద్ధంగా ఉంది. ఇకపై యజమానులకు వెళ్ళే సందేశాలు మీ గొంతులో వెళ్ళవచ్చు. ప్రతి సందేశం ముందుగా అది AI సందేశం అని చెబుతుంది.",
  wordsHeard: (m, t) => ({ before: `${t} మాటల్లో `, bold: String(m), after: " వినిపించాయి" }),
  nameNotHeard: ", మీ పేరు వినిపించలేదు",
  savedInDiary: (when, hash) => `మీ డైరీలో భద్రపరిచాం: ${when} UTC · hash ${hash}…`,
  missed: "వినిపించనివి:",
  baakiHeard: (tr) => `బాకీ విన్నది: “${tr}”`,
  tryAgain: "మళ్ళీ ప్రయత్నించండి",
  confirmByTap: "నేను ఒప్పుకుంటున్నాను, ట్యాప్‌తో నిర్ధారించండి",
  lockNote: "బాకీ గొంతు ప్రొఫైల్‌ను, రికార్డింగ్ వేలిముద్ర (hash) ను మాత్రమే ఉంచుకుంటుంది. రికార్డింగ్‌ను ఎప్పుడూ ఉంచదు.",
  withdrawNote: "మీరు ఎప్పుడైనా మీ అనుమతిని వెనక్కి తీసుకోవచ్చు. దీనితో మీ గొంతు ప్రొఫైల్ తొలగిపోతుంది.",
  withdrawBtn: "అనుమతి వెనక్కి తీసుకుని నా గొంతు తొలగించండి",
  consentRecord: (n) => `అనుమతి రికార్డు (${n})`,
  logWithdrawn: "వెనక్కి తీసుకున్నారు",
  logGiven: (m) => `ఇచ్చారు (${m === "tap" ? "ట్యాప్" : "గొంతు"})`,
};

const hiEn: ConsentUi = {
  title: "Awaaz ki permission",
  eyebrow: "Bas ek baar boliye",
  heroLead: "Aapki awaaz,",
  heroAccent: "aapki marzi.",
  heroSub: "Baaki ke baad yeh line boliye. Wahi recording aapki permission bhi hai aur aapki awaaz ka sample bhi.",
  langGroup: "Bhasha",
  loading: "Load ho raha hai",
  noAudio: "Baaki abhi bol nahi sakta. Screen par likhi line padhiye.",
  readNow: "Ab dheere-dheere padhiye",
  checking: "Aapke shabd check ho rahe hain…",
  sayAfter: "Baaki ke baad yeh boliye",
  loadingShort: "Load ho raha hai…",
  listenFirst: "Pehle suniye",
  stop: "Rokiye",
  recordAgain: "Phir se record",
  record: "Record",
  keepReading: (s) => `Padhte rahiye, kam se kam ${s} second.`,
  profileReady: "Voice profile taiyaar",
  consentOn: (tap, when) => `${when} UTC ko ${tap ? "tap se permission pakki ki" : "awaaz se permission di"}.`,
  consentTap: "Tap se permission pakki hui",
  consentHeard: "Permission sun li",
  readyText:
    "Aapka voice profile taiyaar hai. Ab maalik ko jaane wale messages aapki awaaz mein ja sakte hain, aur har message pehle batata hai ki yeh AI message hai.",
  wordsHeard: (m, t) => ({ before: `${t} mein se `, bold: String(m), after: " shabd sune gaye" }),
  nameNotHeard: ", aapka naam sunai nahi diya",
  savedInDiary: (when, hash) => `Aapki diary mein save hua: ${when} UTC · hash ${hash}…`,
  missed: "Chhoot gaye:",
  baakiHeard: (tr) => `Baaki ne suna: “${tr}”`,
  tryAgain: "Phir se koshish kariye",
  confirmByTap: "Mujhe manzoor hai, tap se pakka karein",
  lockNote: "Baaki sirf voice profile aur recording ka fingerprint (hash) rakhta hai, recording kabhi nahi.",
  withdrawNote: "Aap kabhi bhi apni permission wapas le sakte hain. Isse aapka voice profile delete ho jayega.",
  withdrawBtn: "Permission wapas lo aur meri awaaz delete karo",
  consentRecord: (n) => `Permission ka record (${n})`,
  logWithdrawn: "wapas li",
  logGiven: (m) => `di (${m === "tap" ? "tap" : "awaaz"})`,
};

export const CONSENT_UI: Record<UiLang, ConsentUi> = { en, te, "hi-en": hiEn };
