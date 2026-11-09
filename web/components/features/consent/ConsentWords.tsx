"use client";

// Karaoke-style consent sentence: words turn green (heard) or grey (missed) after the check.
// `cursor` underlines the word being read (from the prompt's playback position or the recording timer).

import type { CSSProperties } from "react";
import type { ConsentWord } from "@/lib/features/consent";

const wrap: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.35em 0.45em",
  fontSize: "1.35rem",
  lineHeight: 1.6,
  color: "var(--text)",
};

function wordStyle(w: ConsentWord, active: boolean): CSSProperties {
  const base: CSSProperties = {
    padding: "0 0.15em",
    borderRadius: "var(--r-xs, 4px)",
    transition: "color 200ms, background-color 200ms",
    borderBottom: active ? "3px solid var(--accent)" : "3px solid transparent",
  };
  if (w.matched === true) return { ...base, color: "var(--success-ink, var(--success))", background: "var(--success-soft)" };
  if (w.matched === false) return { ...base, color: "var(--faint, var(--muted))", textDecoration: "line-through dotted" };
  if (w.kind === "filler") return { ...base, color: "var(--text-2, var(--text))" };
  return { ...base, fontWeight: w.kind === "name" ? 800 : 600 };
}

export function ConsentWords({ words, cursor = null }: { words: ConsentWord[]; cursor?: number | null }) {
  return (
    <p style={wrap} aria-label="Consent sentence">
      {words.map((w) => (
        <span key={w.i} style={wordStyle(w, cursor === w.i)} title={w.heard ? `heard: ${w.heard}` : undefined}>
          {w.text}
        </span>
      ))}
    </p>
  );
}
