"use client";

// The consent sentence, word by word. While Baaki reads it (or while she records) a crisp ink marker follows the
// word being read: words before it are ink, words after it are grey. After the check the words she said light up
// one after another (ink, with an ink underline); missed words stay grey with a dotted underline. No glow.

import type { CSSProperties } from "react";
import type { ConsentWord } from "@/lib/features/consent";
import css from "./consent.module.css";

export function ConsentWords({ words, cursor = null }: { words: ConsentWord[]; cursor?: number | null }) {
  const checked = words.some((w) => w.matched !== null);
  return (
    <p className={css.words} aria-label="Consent sentence" data-mode={checked ? "result" : cursor !== null ? "karaoke" : "idle"}>
      {words.map((w, n) => {
        const pos = cursor === null ? undefined : w.i < cursor ? "before" : w.i === cursor ? "at" : "after";
        const heard = w.matched === true ? "yes" : w.matched === false ? "no" : undefined;
        return (
          <span
            key={w.i}
            className={css.word}
            data-kind={w.kind}
            data-pos={checked ? undefined : pos}
            data-heard={heard}
            style={{ "--n": n } as CSSProperties}
            title={w.heard ? `heard: ${w.heard}` : undefined}
          >
            {w.text}
          </span>
        );
      })}
    </p>
  );
}
