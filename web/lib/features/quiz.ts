// Fair or Not? (V08) client: typed calls to /api/quiz*. Nothing is stored server-side.

import { copyText } from "@/lib/share";

export type QuizLang = "en" | "hi-en" | "te";
export type QuizChoice = "fair" | "not_fair";

export type QuizCard = { id: string; n: number; myth: string; section: string; disclaimer: string };

export type QuizDeck = {
  lang: QuizLang;
  langs: QuizLang[];
  title: string;
  intro: string;
  choices: { id: QuizChoice; label: string }[];
  total: number;
  cards: QuizCard[];
  disclaimer: string;
  disclaimer_en: string;
  check_url: string;
};

export type QuizReveal = {
  id: string;
  n: number;
  myth: string;
  choice: QuizChoice | null;
  answer: QuizChoice;
  answer_label: string;
  correct: boolean | null;
  feedback: string | null;
  rule: string;
  detail: string;
  section: string;
  source: string;
  source_url: string;
  is_estimate: boolean;
  disclaimer: string;
  disclaimer_en: string;
  audio_url: string | null;
  audio_lang: string | null;
};

export type QuizScore = {
  lang: QuizLang;
  score: number;
  total: number;
  answered: number;
  headline: string;
  message: string;
  share_text: string;
  check_url: string;
  check_label: string;
  results: QuizReveal[];
  disclaimer: string;
  disclaimer_en: string;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const b = (await res.json()) as { detail?: unknown };
      if (typeof b.detail === "string") msg = b.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export async function getDeck(lang: QuizLang, signal?: AbortSignal): Promise<QuizDeck> {
  return json(await fetch(`/api/quiz?lang=${encodeURIComponent(lang)}`, { signal, cache: "no-store" }));
}

export async function answerCard(cardId: string, choice: QuizChoice, lang: QuizLang): Promise<QuizReveal> {
  return json(
    await fetch("/api/quiz/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card_id: cardId, choice, lang }),
      cache: "no-store",
    }),
  );
}

export async function scoreQuiz(answers: Record<string, QuizChoice>, lang: QuizLang): Promise<QuizScore> {
  return json(
    await fetch("/api/quiz/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers, lang }),
      cache: "no-store",
    }),
  );
}

export type QuizShareResult = "shared" | "copied" | "cancelled" | "failed";

/** Web Share (text + URL) from a click handler; falls back to copying the text and link. */
export async function shareScore(text: string, url: string, title = "Fair or Not?"): Promise<QuizShareResult> {
  const nav = typeof navigator !== "undefined" ? navigator : null;
  if (nav?.share) {
    try {
      await nav.share({ title, text, url });
      return "shared";
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return "cancelled";
    }
  }
  return (await copyText(`${text} ${url}`)) ? "copied" : "failed";
}
