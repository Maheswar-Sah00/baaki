// V12 Case Replay page strings (the event titles come from the server in en / te / hi).
import type { StoryLang } from "@/lib/features/story";

export type StoryStrings = {
  loading: string;
  kicker: string;
  title: (worker: string, employer: string) => string;
  owed: string;
  of: (total: string) => string;
  play: string;
  replay: string;
  left: (amount: string) => string;
  listen: string;
  listenOriginal: string;
  stop: string;
  paidFull: string;
  stillOwed: (amount: string) => string;
  footnote: string;
};

const EN: StoryStrings = {
  loading: "Loading the case…",
  kicker: "Case replay",
  title: (w, e) => `${w} and ${e}`,
  owed: "Still owed",
  of: (t) => `of ${t}`,
  play: "Play",
  replay: "Replay",
  left: (a) => `${a} left`,
  listen: "▶ Listen",
  listenOriginal: "▶ Their own words",
  stop: "■ Stop",
  paidFull: "Paisa aa gaya! Paid in full.",
  stillOwed: (a) => `${a} is still owed.`,
  footnote: "Every time shown is the time Baaki stored. Nothing is added or moved.",
};

const TE: StoryStrings = {
  loading: "కేసు తెరుస్తున్నాం…",
  kicker: "కేసు మళ్ళీ చూడండి",
  title: (w, e) => `${w}, ${e}`,
  owed: "ఇంకా బాకీ",
  of: (t) => `మొత్తం ${t}`,
  play: "ప్లే",
  replay: "మళ్ళీ ప్లే",
  left: (a) => `${a} మిగిలింది`,
  listen: "▶ వినండి",
  listenOriginal: "▶ వారి మాటలు",
  stop: "■ ఆపండి",
  paidFull: "డబ్బులు వచ్చేశాయి! మొత్తం చెల్లించారు.",
  stillOwed: (a) => `ఇంకా ${a} బాకీ ఉంది.`,
  footnote: "చూపిన ప్రతి సమయం బాకీ యాప్ నమోదు చేసిన సమయమే. ఏదీ కలపలేదు, మార్చలేదు.",
};

const HI: StoryStrings = {
  loading: "केस खुल रहा है…",
  kicker: "केस replay",
  title: (w, e) => `${w} और ${e}`,
  owed: "अभी बाकी",
  of: (t) => `कुल ${t} में से`,
  play: "Play",
  replay: "फिर से play",
  left: (a) => `${a} बाकी`,
  listen: "▶ सुनें",
  listenOriginal: "▶ उनकी अपनी आवाज़",
  stop: "■ रोकें",
  paidFull: "पैसा आ गया! पूरा हिसाब हो गया।",
  stillOwed: (a) => `अभी ${a} बाकी है।`,
  footnote: "हर समय वही है जो Baaki ने दर्ज किया। कुछ जोड़ा या आगे-पीछे नहीं किया।",
};

export function storyStrings(lang: StoryLang): StoryStrings {
  return lang === "te" ? TE : lang === "hi" ? HI : EN;
}
