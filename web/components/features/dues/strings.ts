// Baaki for every promise: strings in Telugu, Hinglish (Devanagari + English words, as in lib/i18n) and English.
import type { UiLang } from "@/lib/i18n";
import type { DuesKind, DuesLang, PromiseStatus } from "@/lib/features/dues";

export type DuesStrings = {
  mountTitle: string;
  mountBody: string;
  title: string;
  heroLabel: string;
  heroSub: (people: number, broken: number) => string;
  add: string;
  demo: string;
  demoLoading: string;
  empty: string;
  emptyHint: string;
  kinds: Record<DuesKind, string>;
  kindHints: Record<DuesKind, string>;
  owes: string;
  promisedTimes: (made: number, broken: number) => string;
  since: (months: number) => string;
  packReady: string;
  // new
  newTitle: string;
  pickKind: string;
  whoOwes: string;
  partyName: string;
  partyPlaceholder: Record<DuesKind, string>;
  partyLang: string;
  langs: Record<DuesLang, string>;
  yourName: string;
  yourUpi: string;
  upiHint: string;
  phone: string;
  sayWhat: string;
  sayHint: Record<DuesKind, string>;
  typePlaceholder: Record<DuesKind, string>;
  tabSpeak: string;
  tabType: string;
  recordStart: string;
  recordStop: string;
  listening: string;
  reading: string;
  readIt: string;
  heard: (t: string) => string;
  runningTotal: string;
  tapToFix: string;
  remove: string;
  promiseHeard: (date: string) => string;
  savePromiseToo: string;
  save: string;
  saving: string;
  noAmount: string;
  back: string;
  next: string;
  // detail
  stillOwed: string;
  counterLine: (made: number, broken: number) => string;
  firstPromised: (date: string, ago: string) => string;
  monthsAgo: (n: number) => string;
  daysAgo: (n: number) => string;
  whatOwed: string;
  received: string;
  timeline: string;
  saidOn: (d: string) => string;
  dueBy: (d: string) => string;
  status: Record<PromiseStatus, string>;
  theyPromised: string;
  promiseSheet: string;
  promiseHint: string;
  promisePlaceholder: string;
  saidOnLabel: string;
  dueLabel: string;
  noDate: string;
  addPromise: string;
  markKept: string;
  markBroken: string;
  gotPaid: string;
  paidSheet: string;
  paidAmount: string;
  remindTitle: string;
  remindHint: (lang: string) => string;
  makeReminder: string;
  withVoice: string;
  voiceNote: string;
  voiceFailed: string;
  checksOk: string;
  inYourLang: string;
  share: string;
  whatsapp: string;
  copied: string;
  upiLink: string;
  youSend: string;
  packTitle: string;
  packBody: (n: number) => string;
  packLocked: (n: number, left: number) => string;
  openPack: string;
  helpLine: string;
  chainOk: (n: number) => string;
  chainBroken: string;
  timeTravel: string;
  today: string;
  error: string;
  retry: string;
  cancel: string;
  notAdvice: string;
};

const EN: DuesStrings = {
  mountTitle: "Someone else owes you?",
  mountBody: "Milk bill, chit money, a hand loan: Baaki keeps every “next week, pakka”.",
  title: "People who owe you",
  heroLabel: "Owed to you",
  heroSub: (p, b) => `${p} ${p === 1 ? "person" : "people"} · ${b} promise${b === 1 ? "" : "s"} not kept`,
  add: "Add someone who owes you",
  demo: "Load the demo",
  demoLoading: "Loading the demo…",
  empty: "Nobody here yet",
  emptyHint: "The milkman's customers, a chit payout, a loan to a friend: add them and Baaki counts every promise.",
  kinds: { vendor: "Milk & daily services", chit: "Chit or promised money", other: "Other" },
  kindHints: {
    vendor: "Customers who owe you for milk, papers, ironing, vegetables",
    chit: "A chit payout, savings or a loan someone promised to return",
    other: "Any money someone keeps promising",
  },
  owes: "owes",
  promisedTimes: (m, b) => `Promised ${m}× · broken ${b}×`,
  since: (n) => (n > 0 ? `since ${n} month${n === 1 ? "" : "s"}` : "this month"),
  packReady: "Record ready",
  newTitle: "Who owes you?",
  pickKind: "What kind of money?",
  whoOwes: "Who owes it",
  partyName: "Their name",
  partyPlaceholder: { vendor: "Reddy garu, flat 302", chit: "Srinivas agent", other: "Name" },
  partyLang: "Their language (the reminder goes in this)",
  langs: { "te-IN": "తెలుగు", "hi-en": "Hinglish", en: "English" },
  yourName: "Your name",
  yourUpi: "Your UPI ID (optional)",
  upiHint: "The reminder carries a pay link to this UPI ID.",
  phone: "Their WhatsApp number (optional)",
  sayWhat: "What do they owe?",
  sayHint: {
    vendor: "Say it like you would: “October doodh 1850, paper 320”.",
    chit: "Say how much and for what: “chit money 40,000”.",
    other: "Say how much and for what.",
  },
  typePlaceholder: { vendor: "October milk 1850, paper 320", chit: "Chit money 40,000", other: "Hand loan 5,000" },
  tabSpeak: "Speak",
  tabType: "Type",
  recordStart: "Tap and speak",
  recordStop: "Tap to stop",
  listening: "Listening…",
  reading: "Reading the amounts…",
  readIt: "Read the amounts",
  heard: (t) => `Heard: “${t}”`,
  runningTotal: "Running total",
  tapToFix: "Tap a chip to fix it",
  remove: "Remove",
  promiseHeard: (d) => `They also said a date: by ${d}`,
  savePromiseToo: "Save that promise too",
  save: "Save and start counting",
  saving: "Saving…",
  noAmount: "No amount heard yet. Try again or type it.",
  back: "Back",
  next: "Next",
  stillOwed: "Still owed",
  counterLine: (m, b) => `Promise made ${m} time${m === 1 ? "" : "s"}, broken ${b} time${b === 1 ? "" : "s"}`,
  firstPromised: (d, a) => `first promised ${d} (${a})`,
  monthsAgo: (n) => `${n} month${n === 1 ? "" : "s"} ago`,
  daysAgo: (n) => (n === 0 ? "today" : `${n} day${n === 1 ? "" : "s"} ago`),
  whatOwed: "What is owed",
  received: "Received",
  timeline: "Every promise, in their words",
  saidOn: (d) => `Said ${d}`,
  dueBy: (d) => `by ${d}`,
  status: { pending: "Waiting", kept: "Kept", broken: "Not kept" },
  theyPromised: "They promised again",
  promiseSheet: "What did they say?",
  promiseHint: "Their words, as said: “next week, pakka”, “1st tareekh”, “ee vaaram chivariki”. Baaki works out the date.",
  promisePlaceholder: "end of this week, pakka",
  saidOnLabel: "Said on",
  dueLabel: "Promised date (if Baaki could not tell)",
  noDate: "No date heard in those words. Pick the promised date below.",
  addPromise: "Save the promise",
  markKept: "Paid on time",
  markBroken: "Not paid",
  gotPaid: "I got paid",
  paidSheet: "How much did you get?",
  paidAmount: "Amount received (₹)",
  remindTitle: "A polite reminder",
  remindHint: (l) => `In their language (${l}). Every amount is checked. No threats, no blame.`,
  makeReminder: "Make the reminder",
  withVoice: "Add a voice note (starts by saying it is an AI voice)",
  voiceNote: "Voice note",
  voiceFailed: "The voice note did not work. The text is ready.",
  checksOk: "Amounts checked",
  inYourLang: "What it says",
  share: "Share",
  whatsapp: "Open WhatsApp",
  copied: "Copied",
  upiLink: "UPI pay link",
  youSend: "Nothing is sent by itself. You choose to send it.",
  packTitle: "Your record is ready",
  packBody: (n) => `${n} promises not kept. A PDF with every promise, the dates, the amounts and the proof codes, plus free legal aid contacts.`,
  packLocked: (n, left) => `After ${n} promises not kept, Baaki makes a record you can take to free legal aid (${left} more).`,
  openPack: "Open the record (PDF)",
  helpLine: "Free legal aid: NALSA 15100 · DLSA Hyderabad",
  chainOk: (n) => `Proof chain intact · ${n} entries`,
  chainBroken: "Proof chain changed: an entry was edited",
  timeTravel: "Demo: see it on",
  today: "Today",
  error: "That did not work. Please try again.",
  retry: "Try again",
  cancel: "Cancel",
  notAdvice: "Baaki is not a lawyer. This is not legal advice.",
};

const HI: DuesStrings = {
  mountTitle: "किसी और का पैसा बाकी है?",
  mountBody: "दूध का bill, चिट का पैसा, उधार: Baaki हर “अगले हफ़्ते, पक्का” याद रखता है।",
  title: "जिन पर आपका पैसा बाकी है",
  heroLabel: "आपका बाकी",
  heroSub: (p, b) => `${p} लोग · ${b} वादे पूरे नहीं हुए`,
  add: "नया नाम जोड़िए",
  demo: "Demo देखिए",
  demoLoading: "Demo आ रहा है…",
  empty: "अभी कोई नाम नहीं",
  emptyHint: "दूध वाले के customers, चिट का पैसा, दोस्त को दिया उधार: जोड़िए, Baaki हर वादा गिनेगा।",
  kinds: { vendor: "दूध और रोज़ की सेवा", chit: "चिट या वादे का पैसा", other: "कुछ और" },
  kindHints: {
    vendor: "दूध, अख़बार, इस्त्री, सब्ज़ी के customers जिन पर बाकी है",
    chit: "चिट का पैसा, बचत या उधार जो लौटाने का वादा हुआ",
    other: "कोई भी पैसा जिसका वादा बार-बार होता है",
  },
  owes: "पर बाकी",
  promisedTimes: (m, b) => `${m} बार वादा · ${b} बार टूटा`,
  since: (n) => (n > 0 ? `${n} महीने से` : "इस महीने"),
  packReady: "Record तैयार",
  newTitle: "किस पर बाकी है?",
  pickKind: "कैसा पैसा है?",
  whoOwes: "किस पर बाकी है",
  partyName: "उनका नाम",
  partyPlaceholder: { vendor: "रेड्डी गारु, flat 302", chit: "श्रीनिवास agent", other: "नाम" },
  partyLang: "उनकी भाषा (याद इसी में जाएगी)",
  langs: { "te-IN": "తెలుగు", "hi-en": "Hinglish", en: "English" },
  yourName: "आपका नाम",
  yourUpi: "आपका UPI ID (चाहें तो)",
  upiHint: "याद के साथ इस UPI ID का pay link जाएगा।",
  phone: "उनका WhatsApp नंबर (चाहें तो)",
  sayWhat: "कितना बाकी है?",
  sayHint: {
    vendor: "जैसे बोलते हैं वैसे बोलिए: “अक्टूबर का दूध 1850, अख़बार 320”।",
    chit: "कितना और किसका: “चिट का पैसा 40,000”।",
    other: "कितना और किसका, बोलिए।",
  },
  typePlaceholder: { vendor: "October doodh 1850, paper 320", chit: "Chit ka paisa 40,000", other: "Udhaar 5,000" },
  tabSpeak: "बोलिए",
  tabType: "लिखिए",
  recordStart: "दबाइए और बोलिए",
  recordStop: "रोकने के लिए दबाइए",
  listening: "सुन रहे हैं…",
  reading: "रकम पढ़ रहे हैं…",
  readIt: "रकम पढ़िए",
  heard: (t) => `सुना: “${t}”`,
  runningTotal: "कुल",
  tapToFix: "ठीक करने के लिए chip दबाइए",
  remove: "हटाइए",
  promiseHeard: (d) => `उन्होंने तारीख़ भी बोली: ${d} तक`,
  savePromiseToo: "यह वादा भी रखिए",
  save: "Save कीजिए, गिनती शुरू",
  saving: "Save हो रहा है…",
  noAmount: "कोई रकम नहीं सुनी। फिर बोलिए या लिखिए।",
  back: "पीछे",
  next: "आगे",
  stillOwed: "अभी बाकी",
  counterLine: (m, b) => `${m} बार वादा किया, ${b} बार नहीं दिया`,
  firstPromised: (d, a) => `पहला वादा ${d} (${a})`,
  monthsAgo: (n) => `${n} महीने पहले`,
  daysAgo: (n) => (n === 0 ? "आज" : `${n} दिन पहले`),
  whatOwed: "क्या बाकी है",
  received: "मिला",
  timeline: "हर वादा, उन्हीं के शब्दों में",
  saidOn: (d) => `${d} को कहा`,
  dueBy: (d) => `${d} तक`,
  status: { pending: "इंतज़ार", kept: "निभाया", broken: "नहीं दिया" },
  theyPromised: "फिर वादा किया",
  promiseSheet: "उन्होंने क्या कहा?",
  promiseHint: "उनके शब्द, जैसे बोले: “अगले हफ़्ते पक्का”, “1 तारीख़ को”। तारीख़ Baaki निकाल लेगा।",
  promisePlaceholder: "is hafte ke end tak, pakka",
  saidOnLabel: "किस दिन कहा",
  dueLabel: "वादे की तारीख़ (अगर Baaki नहीं समझ पाया)",
  noDate: "इन शब्दों में तारीख़ नहीं मिली। नीचे तारीख़ चुनिए।",
  addPromise: "वादा रखिए",
  markKept: "समय पर दिया",
  markBroken: "नहीं दिया",
  gotPaid: "पैसा मिल गया",
  paidSheet: "कितना मिला?",
  paidAmount: "मिली रकम (₹)",
  remindTitle: "आराम से याद दिलाइए",
  remindHint: (l) => `उनकी भाषा में (${l})। हर रकम जाँची गई। कोई धमकी नहीं, कोई इल्ज़ाम नहीं।`,
  makeReminder: "याद तैयार कीजिए",
  withVoice: "Voice note भी (शुरू में बताएगा कि यह AI आवाज़ है)",
  voiceNote: "Voice note",
  voiceFailed: "Voice note नहीं बना। Message तैयार है।",
  checksOk: "रकम जाँची गई",
  inYourLang: "इसमें क्या लिखा है",
  share: "Share",
  whatsapp: "WhatsApp खोलिए",
  copied: "Copy हो गया",
  upiLink: "UPI pay link",
  youSend: "कुछ भी अपने-आप नहीं जाता। भेजना है या नहीं, आप तय करें।",
  packTitle: "आपका record तैयार है",
  packBody: (n) => `${n} वादे पूरे नहीं हुए। हर वादा, तारीख़, रकम और सबूत code वाली PDF, और मुफ़्त legal aid के नंबर।`,
  packLocked: (n, left) => `${n} वादे टूटने पर Baaki एक record बनाएगा जो आप मुफ़्त legal aid के पास ले जा सकें (अभी ${left} और)।`,
  openPack: "Record खोलिए (PDF)",
  helpLine: "मुफ़्त legal aid: NALSA 15100 · DLSA Hyderabad",
  chainOk: (n) => `सबूत की chain सही है · ${n} entries`,
  chainBroken: "सबूत की chain बदली है: एक entry बदली गई",
  timeTravel: "Demo: इस दिन देखिए",
  today: "आज",
  error: "नहीं हो पाया। फिर कोशिश कीजिए।",
  retry: "फिर कोशिश कीजिए",
  cancel: "रहने दो",
  notAdvice: "Baaki वकील नहीं है। यह कानूनी सलाह नहीं है।",
};

const TE: DuesStrings = {
  mountTitle: "ఇంకెవరైనా మీకు బాకీ ఉన్నారా?",
  mountBody: "పాల బిల్లు, చిట్టీ డబ్బులు, అప్పు: ప్రతి “వచ్చే వారం, పక్కా” బాకీ గుర్తు పెట్టుకుంటుంది.",
  title: "మీకు బాకీ ఉన్నవాళ్లు",
  heroLabel: "మీకు రావాల్సింది",
  heroSub: (p, b) => `${p} మంది · ${b} మాటలు నిలబెట్టలేదు`,
  add: "కొత్త పేరు చేర్చండి",
  demo: "డెమో చూడండి",
  demoLoading: "డెమో వస్తోంది…",
  empty: "ఇంకా ఎవరూ లేరు",
  emptyHint: "పాలవాడి కస్టమర్లు, చిట్టీ డబ్బులు, స్నేహితుడికి ఇచ్చిన అప్పు: చేర్చండి, బాకీ ప్రతి మాట లెక్కపెడుతుంది.",
  kinds: { vendor: "పాలు, రోజువారీ సేవలు", chit: "చిట్టీ లేదా మాటిచ్చిన డబ్బు", other: "ఇతర" },
  kindHints: {
    vendor: "పాలు, పేపర్, ఇస్త్రీ, కూరగాయల బాకీ ఉన్న కస్టమర్లు",
    chit: "చిట్టీ డబ్బులు, పొదుపు, లేదా తిరిగి ఇస్తానన్న అప్పు",
    other: "మళ్లీ మళ్లీ మాటిచ్చే ఏ డబ్బైనా",
  },
  owes: "బాకీ",
  promisedTimes: (m, b) => `${m} సార్లు మాట · ${b} సార్లు తప్పింది`,
  since: (n) => (n > 0 ? `${n} నెలలుగా` : "ఈ నెల"),
  packReady: "రికార్డు సిద్ధం",
  newTitle: "ఎవరు బాకీ ఉన్నారు?",
  pickKind: "ఎలాంటి డబ్బు?",
  whoOwes: "ఎవరు బాకీ",
  partyName: "వారి పేరు",
  partyPlaceholder: { vendor: "రెడ్డి గారు, ఫ్లాట్ 302", chit: "శ్రీనివాస్ ఏజెంట్", other: "పేరు" },
  partyLang: "వారి భాష (గుర్తు ఈ భాషలో వెళ్తుంది)",
  langs: { "te-IN": "తెలుగు", "hi-en": "Hinglish", en: "English" },
  yourName: "మీ పేరు",
  yourUpi: "మీ UPI ID (కావాలంటే)",
  upiHint: "గుర్తుతో పాటు ఈ UPI ID కి చెల్లించే లింక్ వెళ్తుంది.",
  phone: "వారి WhatsApp నంబర్ (కావాలంటే)",
  sayWhat: "ఎంత బాకీ?",
  sayHint: {
    vendor: "మామూలుగా చెప్పండి: “అక్టోబర్ పాలు 1850, పేపర్ 320”.",
    chit: "ఎంత, దేనికి: “చిట్టీ డబ్బులు 40,000”.",
    other: "ఎంత, దేనికి చెప్పండి.",
  },
  typePlaceholder: { vendor: "అక్టోబర్ పాలు 1850, పేపర్ 320", chit: "చిట్టీ డబ్బులు 40,000", other: "అప్పు 5,000" },
  tabSpeak: "చెప్పండి",
  tabType: "టైప్ చేయండి",
  recordStart: "నొక్కి మాట్లాడండి",
  recordStop: "ఆపడానికి నొక్కండి",
  listening: "వింటున్నాం…",
  reading: "మొత్తాలు చదువుతున్నాం…",
  readIt: "మొత్తాలు చదవండి",
  heard: (t) => `విన్నది: “${t}”`,
  runningTotal: "మొత్తం",
  tapToFix: "సరిచేయడానికి చిప్ నొక్కండి",
  remove: "తీసేయండి",
  promiseHeard: (d) => `వారు తేదీ కూడా చెప్పారు: ${d} లోపు`,
  savePromiseToo: "ఆ మాట కూడా సేవ్ చేయండి",
  save: "సేవ్ చేసి లెక్క మొదలుపెట్టండి",
  saving: "సేవ్ అవుతోంది…",
  noAmount: "ఇంకా మొత్తం వినలేదు. మళ్లీ చెప్పండి లేదా టైప్ చేయండి.",
  back: "వెనక్కి",
  next: "తర్వాత",
  stillOwed: "ఇంకా రావాలి",
  counterLine: (m, b) => `${m} సార్లు మాటిచ్చారు, ${b} సార్లు ఇవ్వలేదు`,
  firstPromised: (d, a) => `మొదటి మాట ${d} (${a})`,
  monthsAgo: (n) => `${n} నెలల క్రితం`,
  daysAgo: (n) => (n === 0 ? "ఈ రోజు" : `${n} రోజుల క్రితం`),
  whatOwed: "ఏమి బాకీ",
  received: "అందింది",
  timeline: "ప్రతి మాట, వారి మాటల్లోనే",
  saidOn: (d) => `${d} న చెప్పారు`,
  dueBy: (d) => `${d} లోపు`,
  status: { pending: "వేచి ఉంది", kept: "నిలబెట్టారు", broken: "ఇవ్వలేదు" },
  theyPromised: "మళ్లీ మాటిచ్చారు",
  promiseSheet: "వారు ఏమన్నారు?",
  promiseHint: "వారి మాటలు, అన్నట్టే: “వచ్చే వారం పక్కా”, “ఒకటో తారీఖు”, “ఈ వారం చివరికి”. తేదీ బాకీ లెక్కిస్తుంది.",
  promisePlaceholder: "ఈ వారం చివరికి ఇస్తాను",
  saidOnLabel: "ఏ రోజు అన్నారు",
  dueLabel: "మాటిచ్చిన తేదీ (బాకీకి అర్థం కాకపోతే)",
  noDate: "ఈ మాటల్లో తేదీ దొరకలేదు. కింద తేదీ ఎంచుకోండి.",
  addPromise: "మాట సేవ్ చేయండి",
  markKept: "సమయానికి ఇచ్చారు",
  markBroken: "ఇవ్వలేదు",
  gotPaid: "డబ్బు అందింది",
  paidSheet: "ఎంత అందింది?",
  paidAmount: "అందిన మొత్తం (₹)",
  remindTitle: "మర్యాదగా ఒక గుర్తు",
  remindHint: (l) => `వారి భాషలో (${l}). ప్రతి మొత్తం సరిచూశాం. బెదిరింపు లేదు, నింద లేదు.`,
  makeReminder: "గుర్తు తయారు చేయండి",
  withVoice: "వాయిస్ నోట్ కూడా (మొదట ఇది AI గొంతు అని చెబుతుంది)",
  voiceNote: "వాయిస్ నోట్",
  voiceFailed: "వాయిస్ నోట్ రాలేదు. మెసేజ్ సిద్ధంగా ఉంది.",
  checksOk: "మొత్తాలు సరిచూశాం",
  inYourLang: "ఇందులో ఏముంది",
  share: "షేర్",
  whatsapp: "WhatsApp తెరవండి",
  copied: "కాపీ అయింది",
  upiLink: "UPI చెల్లింపు లింక్",
  youSend: "ఏదీ దానంతట అది వెళ్లదు. పంపాలా వద్దా మీరే నిర్ణయించండి.",
  packTitle: "మీ రికార్డు సిద్ధం",
  packBody: (n) => `${n} మాటలు నిలబెట్టలేదు. ప్రతి మాట, తేదీలు, మొత్తాలు, రుజువు కోడ్‌లతో PDF, ఉచిత న్యాయ సహాయం నంబర్లు.`,
  packLocked: (n, left) => `${n} మాటలు తప్పాక, ఉచిత న్యాయ సహాయానికి తీసుకెళ్లగల రికార్డు బాకీ తయారు చేస్తుంది (ఇంకా ${left}).`,
  openPack: "రికార్డు తెరవండి (PDF)",
  helpLine: "ఉచిత న్యాయ సహాయం: NALSA 15100 · DLSA హైదరాబాద్",
  chainOk: (n) => `రుజువు చైన్ సరిగ్గా ఉంది · ${n} ఎంట్రీలు`,
  chainBroken: "రుజువు చైన్ మారింది: ఒక ఎంట్రీ మార్చారు",
  timeTravel: "డెమో: ఈ రోజున చూడండి",
  today: "ఈ రోజు",
  error: "కాలేదు. మళ్లీ ప్రయత్నించండి.",
  retry: "మళ్లీ ప్రయత్నించండి",
  cancel: "వద్దు",
  notAdvice: "బాకీ లాయర్ కాదు. ఇది న్యాయ సలహా కాదు.",
};

const ALL: Record<UiLang, DuesStrings> = { en: EN, "hi-en": HI, te: TE };

export function duesStrings(lang: UiLang): DuesStrings {
  return ALL[lang] ?? EN;
}
