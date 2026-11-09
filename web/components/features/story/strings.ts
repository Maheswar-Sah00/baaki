// V12 Case Replay page strings (the event titles come from the server in en / te / hi).
import type { StoryLang } from "@/lib/features/story";

export type Chapter = "speak" | "letter" | "deal" | "paid";

export type StoryStrings = {
  loading: string;
  kicker: string;
  title: (worker: string, employer: string) => string;
  /** The joining word between the two names in the headline (the serif accent in English). */
  and: string;
  owed: string;
  of: (total: string) => string;
  play: string;
  pause: string;
  resume: string;
  replay: string;
  step: (i: number, n: number) => string;
  left: (amount: string) => string;
  listen: string;
  listenOriginal: string;
  stop: string;
  paidFull: string;
  stillOwed: (amount: string) => string;
  untimed: string;
  footnote: string;
  chapter: Record<Chapter, string>;
};

const EN: StoryStrings = {
  loading: "Loading the case…",
  kicker: "Case replay",
  title: (w, e) => `${w} and ${e}`,
  and: "and",
  owed: "Still owed",
  of: (t) => `of ${t}`,
  play: "Play",
  pause: "Pause",
  resume: "Resume",
  replay: "Replay",
  step: (i, n) => `${i} of ${n}`,
  left: (a) => `${a} left`,
  listen: "Listen",
  listenOriginal: "Their own words",
  stop: "Stop",
  paidFull: "Paisa aa gaya! Paid in full.",
  stillOwed: (a) => `${a} is still owed.`,
  untimed: "Also on record (time not stored)",
  footnote: "Every time shown is the time Baaki stored. Nothing is added or moved.",
  chapter: { speak: "She spoke", letter: "Letter and voice note", deal: "The employer answered", paid: "Paid" },
};

const TE: StoryStrings = {
  loading: "కేసు తెరుస్తున్నాం…",
  kicker: "కేసు మళ్ళీ చూడండి",
  title: (w, e) => `${w}, ${e}`,
  and: "·",
  owed: "ఇంకా బాకీ",
  of: (t) => `మొత్తం ${t}`,
  play: "ప్లే",
  pause: "ఆపండి",
  resume: "కొనసాగించండి",
  replay: "మళ్ళీ ప్లే",
  step: (i, n) => `${i} / ${n}`,
  left: (a) => `${a} మిగిలింది`,
  listen: "వినండి",
  listenOriginal: "వారి మాటలు",
  stop: "ఆపండి",
  paidFull: "డబ్బులు వచ్చేశాయి! మొత్తం చెల్లించారు.",
  stillOwed: (a) => `ఇంకా ${a} బాకీ ఉంది.`,
  untimed: "ఇవి కూడా నమోదయ్యాయి (సమయం లేదు)",
  footnote: "చూపిన ప్రతి సమయం బాకీ యాప్ నమోదు చేసిన సమయమే. ఏదీ కలపలేదు, మార్చలేదు.",
  chapter: { speak: "ఆమె చెప్పింది", letter: "ఉత్తరం, వాయిస్ నోట్", deal: "యజమాని జవాబు", paid: "చెల్లించారు" },
};

const HI: StoryStrings = {
  loading: "केस खुल रहा है…",
  kicker: "केस replay",
  title: (w, e) => `${w} और ${e}`,
  and: "और",
  owed: "अभी बाकी",
  of: (t) => `कुल ${t} में से`,
  play: "Play",
  pause: "रोकें",
  resume: "आगे चलाएँ",
  replay: "फिर से play",
  step: (i, n) => `${i} / ${n}`,
  left: (a) => `${a} बाकी`,
  listen: "सुनें",
  listenOriginal: "उनकी अपनी आवाज़",
  stop: "रोकें",
  paidFull: "पैसा आ गया! पूरा हिसाब हो गया।",
  stillOwed: (a) => `अभी ${a} बाकी है।`,
  untimed: "ये भी दर्ज है (समय नहीं)",
  footnote: "हर समय वही है जो Baaki ने दर्ज किया। कुछ जोड़ा या आगे-पीछे नहीं किया।",
  chapter: { speak: "उन्होंने बताया", letter: "चिट्ठी और voice note", deal: "मालिक का जवाब", paid: "पैसे मिले" },
};

export function storyStrings(lang: StoryLang): StoryStrings {
  return lang === "te" ? TE : lang === "hi" ? HI : EN;
}
