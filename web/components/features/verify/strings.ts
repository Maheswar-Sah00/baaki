// Listen-twice guard strings: Telugu, Hinglish (Devanagari + English words, as in lib/i18n) and English.
import type { UiLang } from "@/lib/i18n";

export type VerifyStrings = {
  checking: string;
  ok: (total: string) => string;
  okNoTotal: string;
  warnTitle: string;
  missing: (list: string) => string;
  extra: (list: string) => string;
  noDisclosure: string;
  advice: string;
  error: string;
  noAudio: string;
  retry: string;
  heard: string;
  took: (s: string) => string;
};

export const VERIFY_STRINGS: Record<UiLang, VerifyStrings> = {
  en: {
    checking: "Baaki is listening to the note again…",
    ok: (t) => `Baaki listened twice: ${t} heard correctly, AI label heard`,
    okNoTotal: "Baaki listened twice: every amount heard correctly, AI label heard",
    warnTitle: "Baaki listened twice and something did not match",
    missing: (l) => `Not heard: ${l}`,
    extra: (l) => `Heard instead: ${l}`,
    noDisclosure: "The AI label at the start was not heard clearly",
    advice: "Play it yourself before sending, or make it again. You can still send it.",
    error: "Baaki could not re-check this note. Play it yourself before sending.",
    noAudio: "This step has no voice note to check.",
    retry: "Check again",
    heard: "What Baaki heard",
    took: (s) => `checked in ${s} s`,
  },
  te: {
    checking: "బాకీ ఈ వాయిస్ నోట్‌ని మళ్ళీ వింటోంది…",
    ok: (t) => `బాకీ రెండుసార్లు విన్నది: ${t} సరిగ్గా వినిపించింది, AI లేబుల్ వినిపించింది`,
    okNoTotal: "బాకీ రెండుసార్లు విన్నది: ప్రతి మొత్తం సరిగ్గా వినిపించింది, AI లేబుల్ వినిపించింది",
    warnTitle: "బాకీ రెండుసార్లు విన్నది, కొంత సరిపోలలేదు",
    missing: (l) => `వినిపించనిది: ${l}`,
    extra: (l) => `బదులుగా వినిపించింది: ${l}`,
    noDisclosure: "మొదట్లో AI లేబుల్ స్పష్టంగా వినిపించలేదు",
    advice: "పంపే ముందు మీరే ఒకసారి వినండి, లేదా మళ్ళీ తయారు చేయండి. అయినా మీరు పంపవచ్చు.",
    error: "బాకీ ఈ నోట్‌ని మళ్ళీ చెక్ చేయలేకపోయింది. పంపే ముందు మీరే వినండి.",
    noAudio: "ఈ దశలో చెక్ చేయడానికి వాయిస్ నోట్ లేదు.",
    retry: "మళ్ళీ చెక్ చేయండి",
    heard: "బాకీకి వినిపించింది",
    took: (s) => `${s} సెకన్లలో చెక్ చేసింది`,
  },
  "hi-en": {
    checking: "Baaki note को दोबारा सुन रहा है…",
    ok: (t) => `Baaki ने दो बार सुना: ${t} सही सुनाई दिया, AI label सुनाई दिया`,
    okNoTotal: "Baaki ने दो बार सुना: हर amount सही सुनाई दिया, AI label सुनाई दिया",
    warnTitle: "Baaki ने दो बार सुना, कुछ मेल नहीं खाया",
    missing: (l) => `सुनाई नहीं दिया: ${l}`,
    extra: (l) => `इसकी जगह सुनाई दिया: ${l}`,
    noDisclosure: "शुरू में AI label साफ़ सुनाई नहीं दिया",
    advice: "भेजने से पहले खुद एक बार सुन लें, या फिर से बनाएँ। फिर भी आप भेज सकते हैं।",
    error: "Baaki इस note को दोबारा check नहीं कर पाया। भेजने से पहले खुद सुन लें।",
    noAudio: "इस step में check करने के लिए voice note नहीं है।",
    retry: "फिर से check करें",
    heard: "Baaki ने क्या सुना",
    took: (s) => `${s} s में check किया`,
  },
};
