// Fair or Not? page chrome. Card text, labels and the disclaimer come from the API (backend/app/quiz_data.py).
import type { QuizLang } from "@/lib/features/quiz";

export const LANG_OPTIONS: { id: QuizLang; label: string }[] = [
  { id: "en", label: "English" },
  { id: "hi-en", label: "Hinglish" },
  { id: "te", label: "తెలుగు" },
];

const en = {
  kicker: "For employers in Hyderabad",
  card: "Card {n} of {total}",
  ask: "Fair or not?",
  next: "Next card",
  finish: "See my score",
  section: "Section",
  source: "Source",
  open_source: "Open the source",
  estimate: "Includes an estimate",
  listen: "Listen in Hinglish (AI voice)",
  your_score: "Your score",
  share: "Share my score",
  shared: "Shared",
  copied: "Copied to clipboard",
  share_failed: "Couldn't share. Copy the link from the address bar.",
  again: "Play again",
  loading: "Loading…",
  error: "Something went wrong. Try again.",
  retry: "Try again",
  you: "You said",
  review: "Your answers",
};

type Dict = typeof en;

const hiEn: Dict = {
  kicker: "Hyderabad के employers के लिए",
  card: "Card {n} / {total}",
  ask: "Fair या not fair?",
  next: "अगला card",
  finish: "मेरा score देखें",
  section: "Section",
  source: "Source",
  open_source: "Source खोलें",
  estimate: "इसमें अनुमान है",
  listen: "Hinglish में सुनें (AI आवाज़)",
  your_score: "आपका score",
  share: "Score share करें",
  shared: "Share हो गया",
  copied: "Clipboard पर copy हो गया",
  share_failed: "Share नहीं हुआ। Address bar से link copy करें।",
  again: "फिर से खेलें",
  loading: "Load हो रहा है…",
  error: "कुछ गड़बड़ हुई। फिर try करें।",
  retry: "फिर try करें",
  you: "आपने कहा",
  review: "आपके जवाब",
};

const te: Dict = {
  kicker: "హైదరాబాద్ యజమానుల కోసం",
  card: "కార్డ్ {n} / {total}",
  ask: "న్యాయమా, కాదా?",
  next: "తర్వాతి కార్డ్",
  finish: "నా స్కోర్ చూడండి",
  section: "సెక్షన్",
  source: "మూలం",
  open_source: "మూలం తెరవండి",
  estimate: "ఇందులో అంచనా ఉంది",
  listen: "హింగ్లీష్‌లో వినండి (AI గొంతు)",
  your_score: "మీ స్కోర్",
  share: "స్కోర్ షేర్ చేయండి",
  shared: "షేర్ అయింది",
  copied: "క్లిప్‌బోర్డ్‌కు కాపీ అయింది",
  share_failed: "షేర్ కాలేదు. అడ్రస్ బార్ నుండి లింక్ కాపీ చేయండి.",
  again: "మళ్ళీ ఆడండి",
  loading: "లోడ్ అవుతోంది…",
  error: "ఏదో తప్పు జరిగింది. మళ్ళీ ప్రయత్నించండి.",
  retry: "మళ్ళీ ప్రయత్నించండి",
  you: "మీరు చెప్పింది",
  review: "మీ జవాబులు",
};

const DICTS: Record<QuizLang, Dict> = { en, "hi-en": hiEn, te };

export type QuizT = (key: keyof Dict, vars?: Record<string, string | number>) => string;

export function makeT(lang: QuizLang): QuizT {
  const d = DICTS[lang] ?? en;
  return (key, vars) => {
    let s = d[key] ?? en[key];
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
    return s;
  };
}
